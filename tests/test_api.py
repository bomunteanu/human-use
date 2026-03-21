"""
Tests for the SSE research endpoint.

All tests mock RapidataClient and anthropic.AsyncAnthropic entirely.
Each test verifies:
  - The endpoint emits the correct event sequence
  - Each event deserializes into the correct typed model
  - order_complete events contain distribution, winner, n_responses
  - done event contains a valid ResearchBrief
"""

from __future__ import annotations

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


async def _collect_events(client: AsyncClient, url: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    async with client.stream("GET", url) as response:
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
# Full flow test: multiple-choice dispatch → complete_research
# ---------------------------------------------------------------------------


async def test_sse_endpoint_emits_correct_event_sequence(
    mock_rapidata: MagicMock,
) -> None:
    # Rapidata: create order
    dispatch_order = _make_order("mc::Which do you prefer?", "ord_mc_1")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    # Rapidata: check_progress and get_results share the same get_order_by_id return
    result_order = _make_order("mc::Which do you prefer?", "ord_mc_1")
    result_order.get_status.return_value = "Completed"
    df = pd.DataFrame({"answer": ["A", "B", "A", "A", "B", "A", "A", "B", "A", "A"]})
    raw_results = MagicMock()
    raw_results.to_pandas.return_value = df
    result_order.get_results.return_value = raw_results
    mock_rapidata.order.get_order_by_id.return_value = result_order

    # Anthropic: first response dispatches ask_multiple_choice
    first_response = _claude_response(
        content=[
            _text_block("I will survey humans about their preference."),
            _tool_use_block(
                name="ask_multiple_choice",
                tool_input={
                    "question": "Which do you prefer?",
                    "options": ["A", "B"],
                    "n": 10,
                },
                tool_id="tu_1",
            ),
        ]
    )

    # Anthropic: second response finishes with complete_research
    second_response = _claude_response(
        content=[
            _tool_use_block(
                name="complete_research",
                tool_input={
                    "summary": "Humans strongly prefer A over B.",
                    "sections": [
                        {
                            "title": "Preference Results",
                            "content": "A received 7/10 votes; B received 3/10.",
                        }
                    ],
                },
                tool_id="tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            events = await _collect_events(
                client,
                "/research/stream?question=Which+do+you+prefer%3F",
            )

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
    df = pd.DataFrame({"answer": ["X", "Y", "X", "X"]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    result_order.get_results.return_value = raw
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
                {
                    "summary": "X wins.",
                    "sections": [{"title": "Result", "content": "X got 3, Y got 1."}],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            raw_events = await _collect_events(client, "/research/stream?question=Test+Q")

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
        assert isinstance(parsed, expected_cls), (
            f"Expected {expected_cls.__name__} for event={raw['event']!r}, "
            f"got {type(parsed).__name__}"
        )


async def test_order_complete_event_contains_distribution_winner_n_responses(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("mc::Favorite color?", "ord_color")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Favorite color?", "ord_color")
    result_order.get_status.return_value = "Completed"
    # 6 red, 3 blue, 1 green
    df = pd.DataFrame(
        {
            "answer": [
                "red",
                "red",
                "red",
                "red",
                "red",
                "red",
                "blue",
                "blue",
                "blue",
                "green",
            ]
        }
    )
    raw = MagicMock()
    raw.to_pandas.return_value = df
    result_order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_multiple_choice",
                {
                    "question": "Favorite color?",
                    "options": ["red", "blue", "green"],
                    "n": 10,
                },
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
                    "sections": [
                        {"title": "Colors", "content": "Red dominated with 6/10."}
                    ],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            raw_events = await _collect_events(
                client, "/research/stream?question=Favorite+color%3F"
            )

    complete_events = [e for e in raw_events if e["event"] == "order_complete"]
    assert len(complete_events) == 1

    parsed = _parse_event(complete_events[0])
    assert isinstance(parsed, OrderCompleteEvent)
    assert parsed.distribution is not None
    assert parsed.distribution["red"] == 6
    assert parsed.distribution["blue"] == 3
    assert parsed.distribution["green"] == 1
    assert parsed.winner == "red"
    assert parsed.n_responses == 10


async def test_done_event_contains_valid_research_brief(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("ft::What do you think?", "ord_ft")
    mock_rapidata.order.create_free_text_order.return_value = dispatch_order

    result_order = _make_order("ft::What do you think?", "ord_ft")
    result_order.get_status.return_value = "Completed"
    df = pd.DataFrame({"response": ["great", "ok", "nice", "good"]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    result_order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "ask_free_text",
                {"question": "What do you think?", "n": 10},
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
                        {
                            "title": "Sentiment",
                            "content": "All four responses were positive.",
                        },
                        {
                            "title": "Themes",
                            "content": "Common words: great, good, nice, ok.",
                        },
                    ],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            raw_events = await _collect_events(
                client, "/research/stream?question=What+do+you+think%3F"
            )

    done_events = [e for e in raw_events if e["event"] == "done"]
    assert len(done_events) == 1

    parsed = _parse_event(done_events[0])
    assert isinstance(parsed, DoneEvent)

    brief = parsed.brief
    assert isinstance(brief, ResearchBrief)
    assert brief.question == "What do you think?"
    assert len(brief.sections) == 2
    assert brief.sections[0].title == "Sentiment"
    assert brief.sections[1].title == "Themes"
    assert brief.summary == "Respondents are generally positive."


async def test_order_complete_compare_has_distribution_and_winner(
    mock_rapidata: MagicMock,
) -> None:
    dispatch_order = _make_order("cmp::Which is better?", "ord_cmp")
    mock_rapidata.order.create_compare_order.return_value = dispatch_order

    result_order = _make_order("cmp::Which is better?", "ord_cmp")
    result_order.get_status.return_value = "Completed"
    # option_a gets 7, option_b gets 3
    df = pd.DataFrame({"a_votes": [7], "b_votes": [3]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    result_order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "compare",
                {
                    "question": "Which is better?",
                    "option_a": "Alpha",
                    "option_b": "Beta",
                    "n": 10,
                },
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
                    "sections": [
                        {"title": "Comparison", "content": "Alpha 7, Beta 3."}
                    ],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            raw_events = await _collect_events(
                client, "/research/stream?question=Which+is+better%3F"
            )

    complete_events = [e for e in raw_events if e["event"] == "order_complete"]
    assert len(complete_events) == 1

    parsed = _parse_event(complete_events[0])
    assert isinstance(parsed, OrderCompleteEvent)
    assert parsed.distribution is not None
    assert parsed.distribution["option_a"] == 7
    assert parsed.distribution["option_b"] == 3
    assert parsed.winner == "option_a"
    assert parsed.n_responses == 10


async def test_event_sequence_order_is_correct(mock_rapidata: MagicMock) -> None:
    dispatch_order = _make_order("mc::Sequence test?", "ord_seq")
    mock_rapidata.order.create_classification_order.return_value = dispatch_order

    result_order = _make_order("mc::Sequence test?", "ord_seq")
    result_order.get_status.return_value = "Completed"
    df = pd.DataFrame({"answer": ["yes", "no", "yes"]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    result_order.get_results.return_value = raw
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
                {
                    "summary": "Yes wins.",
                    "sections": [{"title": "Result", "content": "Yes: 2, No: 1."}],
                },
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            raw_events = await _collect_events(
                client, "/research/stream?question=Sequence+test%3F"
            )

    event_types = [str(e["event"]) for e in raw_events]

    # agent_thought must come before order_dispatched
    idx_thought = event_types.index("agent_thought")
    idx_dispatched = event_types.index("order_dispatched")
    assert idx_thought < idx_dispatched

    # order_dispatched before order_progress
    idx_progress = event_types.index("order_progress")
    assert idx_dispatched < idx_progress

    # order_progress before order_complete
    idx_complete = event_types.index("order_complete")
    assert idx_progress < idx_complete

    # order_complete before brief_update
    idx_brief = event_types.index("brief_update")
    assert idx_complete < idx_brief

    # brief_update before done
    idx_done = event_types.index("done")
    assert idx_brief < idx_done
