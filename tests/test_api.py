"""
Tests for the SSE research endpoint, clarifying question flow, and compile endpoint.

All tests mock RapidataClient and anthropic.AsyncAnthropic entirely.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter

import human_use.client as client_module
from human_use.api import app
from human_use.models import (
    AgentThoughtEvent,
    BriefUpdateEvent,
    ClarifyingQuestionEvent,
    DoneEvent,
    OrderCompleteEvent,
    OrderDispatchedEvent,
    OrderProgressEvent,
    ResearchBrief,
    SSEEvent,
)

_SSEEventAdapter: TypeAdapter[SSEEvent] = TypeAdapter(SSEEvent)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_client():
    client_module._client = None
    yield
    client_module._client = None


@pytest.fixture(autouse=True)
def reset_pending():
    import human_use.api as api_module
    api_module._pending_events.clear()
    api_module._pending_answers.clear()
    yield
    api_module._pending_events.clear()
    api_module._pending_answers.clear()


@pytest.fixture
def mock_rapidata(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("human_use.client.RapidataClient", lambda **kw: mock)
    monkeypatch.setenv("RAPIDATA_CLIENT_ID", "test_id")
    monkeypatch.setenv("RAPIDATA_CLIENT_SECRET", "test_secret")
    return mock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order(name: str, order_id: str = "ord_test") -> MagicMock:
    order = MagicMock()
    order.id = order_id
    order.name = name
    order.run.return_value = order
    return order


def _tool_use_block(
    name: str,
    tool_input: dict[str, object],
    tool_id: str = "tu_1",
) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = tool_input
    return block


def _text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _claude_response(
    content: list[MagicMock],
    stop_reason: str = "tool_use",
) -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content
    return response


def _mc_df(*options_and_counts: tuple[str, int]) -> pd.DataFrame:
    """Build a DataFrame with aggregatedResults_<option> columns as get_results expects."""
    return pd.DataFrame(
        {f"aggregatedResults_{opt}": [count] for opt, count in options_and_counts}
    )


async def _collect_events(
    client: AsyncClient,
    question: str,
    session_id: str = "test_session",
    messages: list[dict] | None = None,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    body: dict[str, object] = {"question": question, "session_id": session_id}
    if messages is not None:
        body["messages"] = messages
    async with client.stream(
        "POST",
        "/research/stream",
        json=body,
    ) as response:
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data: "):
                payload = line[6:]
                if payload:
                    try:
                        events.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass
    return events


async def _collect_compile_events(
    client: AsyncClient,
    messages: list[dict],
    session_id: str = "compile_session",
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    async with client.stream(
        "POST",
        "/research/compile",
        json={"session_id": session_id, "messages": messages},
    ) as response:
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data: "):
                payload = line[6:]
                if payload:
                    try:
                        events.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass
    return events


def _parse_event(data: dict[str, object]) -> SSEEvent:
    return _SSEEventAdapter.validate_python(data)


# ---------------------------------------------------------------------------
# Full flow tests
# ---------------------------------------------------------------------------


async def test_sse_endpoint_emits_correct_event_sequence(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("mc::Which do you prefer?", "ord_mc_1")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Which do you prefer?", "ord_mc_1")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("A", 7), ("B", 3))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _text_block("I will survey humans about their preference."),
            _tool_use_block(
                name="ask_multiple_choice",
                tool_input={"question": "Which do you prefer?", "options": ["A", "B"], "n": 10},
                tool_id="tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                name="complete_research",
                tool_input={
                    "summary": "Humans strongly prefer A over B.",
                    "sections": [{"title": "Preference Results", "content": "A: 7, B: 3."}],
                },
                tool_id="tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Which do you prefer?")

    event_types = [e["event"] for e in events]
    assert "agent_thought" in event_types
    assert "order_dispatched" in event_types
    assert "order_progress" in event_types
    assert "order_complete" in event_types
    assert "brief_update" in event_types
    assert "done" in event_types


async def test_each_event_deserializes_into_correct_typed_model(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("mc::Test Q", "ord_1")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Test Q", "ord_1")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("X", 3), ("Y", 1))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _text_block("Dispatching poll."),
            _tool_use_block(
                "ask_multiple_choice",
                {"question": "Test Q", "options": ["X", "Y"], "n": 10},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "X wins.", "sections": [{"title": "Result", "content": "X: 3, Y: 1."}]},
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            raw_events = await _collect_events(client, "Test Q")

    type_map = {
        "agent_thought": AgentThoughtEvent,
        "order_dispatched": OrderDispatchedEvent,
        "order_progress": OrderProgressEvent,
        "order_complete": OrderCompleteEvent,
        "brief_update": BriefUpdateEvent,
        "done": DoneEvent,
    }

    for raw in raw_events:
        parsed = _parse_event(raw)
        expected_cls = type_map[str(raw["event"])]
        assert isinstance(parsed, expected_cls)


async def test_order_complete_event_contains_distribution_winner_n_responses(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("mc::Favorite color?", "ord_color")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Favorite color?", "ord_color")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("red", 6), ("blue", 3), ("green", 1))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_multiple_choice",
                {"question": "Favorite color?", "options": ["red", "blue", "green"], "n": 10},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {
                    "summary": "Red is the favorite.",
                    "sections": [{"title": "Colors", "content": "Red: 6/10."}],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            raw_events = await _collect_events(client, "Favorite color?")

    complete_events = [e for e in raw_events if e["event"] == "order_complete"]
    assert len(complete_events) == 1

    parsed = _parse_event(complete_events[0])
    assert isinstance(parsed, OrderCompleteEvent)
    assert parsed.distribution == {"red": 6, "blue": 3, "green": 1}
    assert parsed.winner == "red"
    assert parsed.n_responses == 10


async def test_done_event_contains_valid_research_brief(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("mc::What do you prefer?", "ord_mc")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::What do you prefer?", "ord_mc")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("A", 7), ("B", 3))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_multiple_choice",
                {"question": "What do you prefer?", "options": ["A", "B"], "n": 10},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {
                    "summary": "Respondents are generally positive.",
                    "sections": [
                        {"title": "Sentiment", "content": "All four responses were positive."},
                        {"title": "Themes", "content": "Common words: great, good, nice, ok."},
                    ],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            raw_events = await _collect_events(client, "What do you prefer?")

    done_events = [e for e in raw_events if e["event"] == "done"]
    assert len(done_events) == 1

    parsed = _parse_event(done_events[0])
    assert isinstance(parsed, DoneEvent)
    brief = parsed.brief
    assert isinstance(brief, ResearchBrief)
    assert brief.question == "What do you prefer?"
    assert len(brief.sections) == 2
    assert brief.sections[0].title == "Sentiment"
    assert brief.sections[1].title == "Themes"
    assert brief.summary == "Respondents are generally positive."


async def test_done_event_includes_messages_array(
    mock_rapidata: MagicMock,
) -> None:
    """done event carries a non-empty messages array for conversation history."""
    dispatch_order = _make_order("mc::Test history?", "ord_hist")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Test history?", "ord_hist")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("yes", 8), ("no", 2))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_multiple_choice",
                {"question": "Test history?", "options": ["yes", "no"], "n": 10},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "Yes wins.", "sections": [{"title": "R", "content": "C."}]},
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            raw_events = await _collect_events(client, "Test history?")

    done_events = [e for e in raw_events if e["event"] == "done"]
    assert len(done_events) == 1

    parsed = _parse_event(done_events[0])
    assert isinstance(parsed, DoneEvent)
    assert isinstance(parsed.messages, list)
    assert len(parsed.messages) > 0
    # First message should be the user's research question
    assert parsed.messages[0]["role"] == "user"
    assert "Test history?" in str(parsed.messages[0]["content"])


async def test_prior_messages_are_prepended_to_conversation(
    mock_rapidata: MagicMock,
) -> None:
    """Messages from a previous session are passed to the Anthropic API."""
    dispatch_order = _make_order("mc::Follow-up?", "ord_fu")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Follow-up?", "ord_fu")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("A", 5), ("B", 5))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    received_messages: list[list[object]] = []

    async def capturing_create(**kwargs: object) -> MagicMock:
        received_messages.append(list(kwargs.get("messages", [])))
        if len(received_messages) == 1:
            return _claude_response(
                content=[
                    _tool_use_block(
                        "ask_multiple_choice",
                        {"question": "Follow-up?", "options": ["A", "B"], "n": 10},
                        "tu_1",
                    ),
                ]
            )
        return _claude_response(
            content=[
                _tool_use_block(
                    "complete_research",
                    {"summary": "Tie.", "sections": [{"title": "R", "content": "C."}]},
                    "tu_2",
                ),
            ]
        )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=capturing_create)

    prior = [
        {"role": "user", "content": "Research question: Previous topic\n\nPlease research."},
        {"role": "assistant", "content": [{"type": "text", "text": "Previous answer."}]},
    ]

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _collect_events(client, "Follow-up question?", messages=prior)

    assert len(received_messages) >= 1
    first_call_messages = received_messages[0]
    # Prior messages should appear at the start
    assert first_call_messages[0] == prior[0]
    assert first_call_messages[1] == prior[1]
    # New research question appended after prior messages
    assert first_call_messages[2]["role"] == "user"
    assert "Follow-up question?" in str(first_call_messages[2]["content"])


async def test_order_complete_compare_has_distribution_and_winner(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("cmp::Which is better?", "ord_cmp")
    mock_rapidata.order.create_compare_order.return_value = dispatch_order

    result_order = _make_order("cmp::Which is better?", "ord_cmp")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: pd.DataFrame({"a_votes": [7], "b_votes": [3]})
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "compare",
                {"question": "Which is better?", "option_a": "Alpha", "option_b": "Beta", "n": 10},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {
                    "summary": "Alpha is preferred.",
                    "sections": [{"title": "Comparison", "content": "Alpha 7, Beta 3."}],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            raw_events = await _collect_events(client, "Which is better?")

    complete_events = [e for e in raw_events if e["event"] == "order_complete"]
    assert len(complete_events) == 1

    parsed = _parse_event(complete_events[0])
    assert isinstance(parsed, OrderCompleteEvent)
    assert parsed.distribution == {"option_a": 7, "option_b": 3}
    assert parsed.winner == "option_a"
    assert parsed.n_responses == 10


async def test_event_sequence_order_is_correct(mock_rapidata: MagicMock) -> None:
    dispatch_order = _make_order("mc::Sequence test?", "ord_seq")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Sequence test?", "ord_seq")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("yes", 2), ("no", 1))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _text_block("Starting research."),
            _tool_use_block(
                "ask_multiple_choice",
                {"question": "Sequence test?", "options": ["yes", "no"], "n": 10},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "Yes wins.", "sections": [{"title": "Result", "content": "Yes: 2, No: 1."}]},
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            raw_events = await _collect_events(client, "Sequence test?")

    event_types = [str(e["event"]) for e in raw_events]

    idx_thought = event_types.index("agent_thought")
    idx_dispatched = event_types.index("order_dispatched")
    assert idx_thought < idx_dispatched

    idx_progress = event_types.index("order_progress")
    assert idx_dispatched < idx_progress

    idx_complete = event_types.index("order_complete")
    assert idx_progress < idx_complete

    idx_brief = event_types.index("brief_update")
    assert idx_complete < idx_brief

    idx_done = event_types.index("done")
    assert idx_brief < idx_done


# ---------------------------------------------------------------------------
# Compile endpoint tests
# ---------------------------------------------------------------------------


async def test_compile_endpoint_emits_brief_and_done() -> None:
    """POST /research/compile streams brief_update and done events."""
    compile_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {
                    "summary": "Synthesized findings.",
                    "sections": [
                        {"title": "Key Insights", "content": "People prefer option A."},
                        {"title": "Demographics", "content": "Mainly 18-35 age group."},
                    ],
                },
                "tu_compile",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=compile_response)

    prior_messages = [
        {"role": "user", "content": "Research question: Which option do people prefer?\n\nPlease research."},
        {"role": "assistant", "content": [{"type": "text", "text": "I will survey people."}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ord_1"}]},
    ]

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_compile_events(client, prior_messages)

    event_types = [e["event"] for e in events]
    assert "brief_update" in event_types
    assert "done" in event_types
    assert event_types.index("brief_update") < event_types.index("done")


async def test_compile_endpoint_produces_correct_brief_content() -> None:
    """Compile endpoint synthesizes all messages into a well-structured brief."""
    compile_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {
                    "summary": "Users strongly prefer dark mode.",
                    "sections": [
                        {"title": "Preference", "content": "80% prefer dark mode."},
                        {"title": "Reasons", "content": "Eye strain cited by 60%."},
                    ],
                },
                "tu_c",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=compile_response)

    messages = [
        {"role": "user", "content": "Research question: Dark vs light mode?\n\nPlease research."},
        {"role": "assistant", "content": [{"type": "text", "text": "Dispatching survey."}]},
    ]

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_compile_events(client, messages)

    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1

    parsed = _parse_event(done_events[0])
    assert isinstance(parsed, DoneEvent)
    brief = parsed.brief
    assert isinstance(brief, ResearchBrief)
    assert brief.summary == "Users strongly prefer dark mode."
    assert len(brief.sections) == 2
    assert brief.sections[0].title == "Preference"
    assert brief.sections[1].title == "Reasons"


async def test_compile_receives_full_conversation_history() -> None:
    """Compile passes all provided messages directly to the Anthropic API."""
    received_messages: list[list[object]] = []

    async def capturing_create(**kwargs: object) -> MagicMock:
        received_messages.append(list(kwargs.get("messages", [])))
        return _claude_response(
            content=[
                _tool_use_block(
                    "complete_research",
                    {"summary": "Done.", "sections": [{"title": "R", "content": "C."}]},
                    "tu_c",
                ),
            ]
        )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=capturing_create)

    input_messages = [
        {"role": "user", "content": "Research question: Topic A\n\nPlease research."},
        {"role": "assistant", "content": [{"type": "text", "text": "Thought 1."}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "result1"}]},
    ]

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _collect_compile_events(client, input_messages)

    assert len(received_messages) == 1
    assert len(received_messages[0]) == len(input_messages)
    assert received_messages[0][0] == input_messages[0]


async def test_compile_extracts_question_from_first_user_message() -> None:
    """Compile brief question is extracted from the first user message."""
    compile_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "Done.", "sections": [{"title": "R", "content": "C."}]},
                "tu_c",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=compile_response)

    messages = [
        {"role": "user", "content": "Research question: Brand awareness study\n\nPlease research."},
    ]

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_compile_events(client, messages)

    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1
    parsed = _parse_event(done_events[0])
    assert isinstance(parsed, DoneEvent)
    assert parsed.brief.question == "Brand awareness study"


# ---------------------------------------------------------------------------
# Clarifying question tests
#
# ASGITransport buffers the entire SSE response before returning it, so
# concurrent "POST /research/answer" requests from inside the stream reader
# would deadlock. Instead, we pre-populate _pending_answers before the stream
# starts. _await_answer checks that dict first and returns immediately — no
# blocking, no deadlock.
# ---------------------------------------------------------------------------

import human_use.api as _api_module


def _pre_answer(session_id: str, answers: dict[int, str]) -> None:
    """Pre-populate answers so _await_answer returns without waiting."""
    for q_idx, answer in answers.items():
        _api_module._pending_answers[(session_id, q_idx)] = answer


async def test_clarifying_question_event_is_emitted(mock_rapidata: MagicMock) -> None:
    """Agent emits clarifying_question SSE event and then proceeds to dispatch a survey."""
    dispatch_order = _make_order("mc::What do you prefer?", "ord_mc_cq")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::What do you prefer?", "ord_mc_cq")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("A", 2), ("B", 1))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _text_block("Let me clarify the scope first."),
            _tool_use_block(
                "ask_clarifying_question",
                {"question": "What age group are you targeting?", "options": ["18-25", "26-40", "41+"]},
                "tu_cq_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_multiple_choice",
                {"question": "What do you prefer?", "options": ["A", "B"], "n": 10},
                "tu_mc_1",
            ),
        ]
    )
    third_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "A wins.", "sections": [{"title": "Result", "content": "A: 2, B: 1."}]},
                "tu_cr_1",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response, third_response])

    session_id = "test_cq_emitted"
    _pre_answer(session_id, {0: "18-25"})

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Research question", session_id)

    event_types = [e["event"] for e in events]
    assert "clarifying_question" in event_types
    assert "order_dispatched" in event_types
    assert "done" in event_types
    assert event_types.index("clarifying_question") < event_types.index("order_dispatched")


async def test_clarifying_question_event_deserializes_correctly(
    mock_rapidata: MagicMock,
) -> None:
    """clarifying_question SSE event deserializes into ClarifyingQuestionEvent."""
    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_clarifying_question",
                {"question": "Which industry?", "options": ["Tech", "Finance", "Healthcare"]},
                "tu_cq_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "Done.", "sections": [{"title": "Result", "content": "Research complete."}]},
                "tu_cr_1",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    session_id = "test_cq_deser"
    _pre_answer(session_id, {0: "Tech"})

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Industry research", session_id)

    cq_events = [e for e in events if e.get("event") == "clarifying_question"]
    assert len(cq_events) == 1

    parsed = _parse_event(cq_events[0])
    assert isinstance(parsed, ClarifyingQuestionEvent)
    assert parsed.question == "Which industry?"
    assert parsed.session_id == session_id
    assert parsed.question_index == 0
    assert len(parsed.options) == 4
    assert "Other (please specify)" in parsed.options
    assert "Tech" in parsed.options


async def test_research_answer_endpoint_resolves_pending_event() -> None:
    """POST /research/answer sets the asyncio.Event and returns {ok: true}."""
    session_id = "test_answer_ep"
    q_idx = 0

    ev = asyncio.Event()
    _api_module._pending_events[(session_id, q_idx)] = ev

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/research/answer",
            json={"session_id": session_id, "question_index": q_idx, "answer": "Finance"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert ev.is_set()
    assert _api_module._pending_answers.get((session_id, q_idx)) == "Finance"


async def test_agent_receives_clarifying_answer_before_proceeding(
    mock_rapidata: MagicMock,
) -> None:
    """The clarifying answer string is returned by _await_answer and passed as the tool result."""
    dispatch_order = _make_order("mc::Refined question", "ord_refined")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Refined question", "ord_refined")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = MagicMock(
        to_pandas=lambda: _mc_df(("yes", 2), ("no", 1))
    )
    mock_rapidata.order.get_order_by_id.return_value = result_order

    received_tool_results: list[dict[str, object]] = []
    call_idx = 0

    async def capturing_create(**kwargs: object) -> MagicMock:
        nonlocal call_idx
        # Capture tool_results from the last user message only
        for msg in reversed(list(kwargs.get("messages", []))):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_result":
                            received_tool_results.append(item)
                break

        idx = call_idx
        call_idx += 1

        if idx == 0:
            return _claude_response(
                content=[
                    _tool_use_block(
                        "ask_clarifying_question",
                        {"question": "Who is the target?", "options": ["Consumers", "Businesses", "Both"]},
                        "tu_cq_1",
                    ),
                ]
            )
        elif idx == 1:
            return _claude_response(
                content=[
                    _tool_use_block(
                        "ask_multiple_choice",
                        {"question": "Refined question", "options": ["yes", "no"], "n": 10},
                        "tu_mc_1",
                    ),
                ]
            )
        else:
            return _claude_response(
                content=[
                    _tool_use_block(
                        "complete_research",
                        {"summary": "Done.", "sections": [{"title": "R", "content": "C."}]},
                        "tu_cr_1",
                    ),
                ]
            )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=capturing_create)

    session_id = "test_answer_flow"
    _pre_answer(session_id, {0: "Consumers"})

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Target audience research", session_id)

    event_types = [e["event"] for e in events]
    assert event_types.index("clarifying_question") < event_types.index("order_dispatched")

    assert any(
        r.get("content") == "Consumers" for r in received_tool_results
    ), f"Expected 'Consumers' in tool results, got: {received_tool_results}"


async def test_clarifying_question_options_include_other(
    mock_rapidata: MagicMock,
) -> None:
    """Backend always appends 'Other (please specify)' as the fourth option."""
    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_clarifying_question",
                {"question": "What matters most?", "options": ["Price", "Quality", "Speed"]},
                "tu_cq_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"summary": "Done.", "sections": [{"title": "R", "content": "C."}]},
                "tu_cr_1",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    session_id = "test_options_other"
    _pre_answer(session_id, {0: "Price"})

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "What matters?", session_id)

    cq_events = [e for e in events if e.get("event") == "clarifying_question"]
    assert len(cq_events) == 1

    options = cq_events[0]["options"]
    assert len(options) == 4
    assert options[:3] == ["Price", "Quality", "Speed"]
    assert options[3] == "Other (please specify)"


# ---------------------------------------------------------------------------
# Session persistence tests (use conftest.py fixtures: db_session, client)
# ---------------------------------------------------------------------------


def _complete_research_mock():
    """Return a mock Anthropic client that immediately calls complete_research."""
    mock_client = MagicMock()
    response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {
                    "summary": "Summary.",
                    "sections": [{"title": "Section", "content": "Content."}],
                },
                "tu_cr_persist",
            ),
        ]
    )
    mock_client.messages.create = AsyncMock(return_value=response)
    return mock_client


async def _stream_with_auth(client, question: str, session_id: str, token: str | None) -> list[dict]:
    """Stream /research/stream and collect all events, optionally with auth."""
    events: list[dict] = []
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with client.stream(
        "POST",
        "/research/stream",
        json={"question": question, "session_id": session_id},
        headers=headers,
    ) as response:
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data: "):
                payload = line[6:]
                if payload:
                    try:
                        events.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass
    return events


async def test_session_persisted_on_done_when_authenticated(
    client,
    db_session,
    mock_rapidata,
):
    """Session + messages are written to DB when done fires with valid JWT."""
    # Register user and get token
    res = await client.post(
        "/auth/register", json={"email": "persist@test.com", "password": "password1"}
    )
    token = res.json()["access_token"]
    question = "What do people prefer?"
    session_id = "550e8400-e29b-41d4-a716-446655440000"

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=_complete_research_mock()):
        events = await _stream_with_auth(client, question, session_id, token)

    done_events = [e for e in events if e.get("event") == "done"]
    assert len(done_events) == 1

    from human_use.crud import get_sessions, get_user_by_email
    import uuid
    user = await get_user_by_email(db_session, "persist@test.com")
    assert user is not None
    sessions = await get_sessions(db_session, user.id)
    assert len(sessions) == 1
    assert sessions[0].title == question[:60]
    assert str(sessions[0].id) == session_id


async def test_session_not_persisted_without_auth(
    client,
    db_session,
    mock_rapidata,
):
    """No DB write when /research/stream is called without a JWT."""
    # Register so we can verify no session was created for ANY user
    res = await client.post(
        "/auth/register", json={"email": "noauth@test.com", "password": "password1"}
    )
    token = res.json()["access_token"]

    question = "Unauthenticated question"
    session_id = "660e8400-e29b-41d4-a716-446655440001"

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=_complete_research_mock()):
        events = await _stream_with_auth(client, question, session_id, token=None)

    done_events = [e for e in events if e.get("event") == "done"]
    assert len(done_events) == 1

    from human_use.crud import get_sessions, get_user_by_email
    user = await get_user_by_email(db_session, "noauth@test.com")
    assert user is not None
    sessions = await get_sessions(db_session, user.id)
    assert len(sessions) == 0
