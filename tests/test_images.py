"""
Tests for AI image generation with human A/B testing.

Mocks google.genai.Client and RapidataClient entirely — no real API calls.
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter

import human_use.client as client_module
from human_use.api import app
from human_use.models import (
    ImagesGeneratedEvent,
    OrderCompleteEvent,
    SSEEvent,
)
from human_use.tools import (
    ImageGenerateResult,
    _parse_order_result,
    generate_and_compare_images,
)

_SSEEventAdapter: TypeAdapter[SSEEvent] = TypeAdapter(SSEEvent)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_IMG_A = b"\x89PNG\r\n\x1a\nfake_image_a_bytes"
FAKE_IMG_B = b"\x89PNG\r\n\x1a\nfake_image_b_bytes"
FAKE_IMG_A_B64 = base64.b64encode(FAKE_IMG_A).decode()
FAKE_IMG_B_B64 = base64.b64encode(FAKE_IMG_B).decode()


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


def _make_genai_response(image_bytes: bytes) -> MagicMock:
    """Build a mock generate_content response carrying one inline image part."""
    part = MagicMock()
    part.inline_data = MagicMock()
    part.inline_data.data = image_bytes
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.candidates = [candidate]
    return response


@pytest.fixture
def mock_genai(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock google.genai.Client to return predictable fake image bytes."""
    call_count = 0

    def _client_factory(api_key: str) -> MagicMock:
        nonlocal call_count
        mock_client = MagicMock()
        # Alternate A/B bytes based on call order so we can distinguish them
        image_bytes = FAKE_IMG_A if call_count % 2 == 0 else FAKE_IMG_B
        mock_client.models.generate_content.return_value = _make_genai_response(image_bytes)
        call_count += 1
        return mock_client

    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setattr("human_use.tools.genai.Client", _client_factory)
    return _client_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_img_order(order_id: str = "img_ord_1") -> MagicMock:
    order = MagicMock()
    order.id = order_id
    order.name = f"img::Which image is better?"
    order.run.return_value = order
    return order


def _cmp_df(a_votes: int, b_votes: int) -> MagicMock:
    """Build a mock RapidataResults object for a compare order."""
    df = pd.DataFrame({"A_choice": [a_votes], "B_choice": [b_votes]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    raw.get.return_value = []
    return raw


def _tool_use_block(name: str, tool_input: dict, tool_id: str = "tu_1") -> MagicMock:
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


def _claude_response(content: list[MagicMock], stop_reason: str = "tool_use") -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content
    return response


async def _collect_events(
    client: AsyncClient,
    question: str,
    session_id: str = "test_img_session",
) -> list[dict]:
    events: list[dict] = []
    async with client.stream(
        "POST",
        "/research/stream",
        json={"question": question, "session_id": session_id},
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


# ---------------------------------------------------------------------------
# Unit tests: _parse_order_result for img:: prefix
# ---------------------------------------------------------------------------


def test_parse_img_order_result_routes_to_compare_parser():
    """img:: prefix should be parsed identically to cmp:: (A_*/B_* column logic)."""
    raw = _cmp_df(a_votes=30, b_votes=20)
    result = _parse_order_result("img_ord_1", "img::Which image is better?", raw)

    from human_use.models import CompareResult

    assert isinstance(result, CompareResult)
    assert result.order_id == "img_ord_1"
    assert result.option_a_votes == 30
    assert result.option_b_votes == 20
    assert result.winner == "option_a"
    assert result.n_responses == 50
    assert 0.0 <= result.confidence <= 1.0


def test_parse_img_order_result_b_wins():
    raw = _cmp_df(a_votes=10, b_votes=40)
    result = _parse_order_result("img_ord_2", "img::Better logo?", raw)

    from human_use.models import CompareResult

    assert isinstance(result, CompareResult)
    assert result.winner == "option_b"
    assert result.option_b_votes == 40


# ---------------------------------------------------------------------------
# Unit tests: generate_and_compare_images tool
# ---------------------------------------------------------------------------


async def test_generate_and_compare_images_returns_image_generate_result(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """generate_and_compare_images returns ImageGenerateResult with img:: order_id."""
    compare_order = _make_img_order("img_abc123")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    result = await generate_and_compare_images(
        prompt_a="A minimalist blue logo for a fintech startup",
        prompt_b="A bold red logo for a fintech startup",
        question="Which logo better represents trust?",
    )

    assert isinstance(result, ImageGenerateResult)
    assert result.order_id == "img_abc123"
    assert result.prompt_a == "A minimalist blue logo for a fintech startup"
    assert result.prompt_b == "A bold red logo for a fintech startup"
    # Both images should be non-empty base64
    assert len(result.image_a_b64) > 0
    assert len(result.image_b_b64) > 0
    # Should be valid base64
    base64.b64decode(result.image_a_b64)
    base64.b64decode(result.image_b_b64)


async def test_generate_and_compare_images_calls_imagen_in_parallel(
    mock_rapidata: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both images must be generated — two calls to generate_images total."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_key")
    compare_order = _make_img_order("img_par1")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    call_log: list[str] = []

    def _client_factory(api_key: str) -> MagicMock:
        mock_client = MagicMock()

        def _gen(model: str, contents: str, config) -> MagicMock:
            call_log.append(contents)
            return _make_genai_response(f"bytes_for_{contents}".encode())

        mock_client.models.generate_content.side_effect = _gen
        return mock_client

    monkeypatch.setattr("human_use.tools.genai.Client", _client_factory)

    result = await generate_and_compare_images(
        prompt_a="prompt_alpha",
        prompt_b="prompt_beta",
        question="Which is better?",
    )

    assert "prompt_alpha" in call_log
    assert "prompt_beta" in call_log
    assert len(call_log) == 2
    assert result.image_a_b64 == base64.b64encode(b"bytes_for_prompt_alpha").decode()
    assert result.image_b_b64 == base64.b64encode(b"bytes_for_prompt_beta").decode()


async def test_generate_and_compare_images_creates_compare_order_with_contexts(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """Rapidata compare order must use file paths and include contexts=[question]."""
    compare_order = _make_img_order("img_ctx1")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    await generate_and_compare_images(
        prompt_a="Modern UI design",
        prompt_b="Classic UI design",
        question="Which UI feels more professional?",
    )

    call_kwargs = mock_rapidata.order.create_compare_order.call_args
    assert call_kwargs is not None
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]

    # Order name must have img:: prefix
    assert kwargs.get("name", "").startswith("img::")
    # contexts must be provided
    assert kwargs.get("contexts") == ["Which UI feels more professional?"]
    # datapoints must be a list of pairs
    datapoints = kwargs.get("datapoints", [])
    assert len(datapoints) == 1
    assert len(datapoints[0]) == 2
    # Both datapoints should be strings (file paths)
    assert all(isinstance(p, str) for p in datapoints[0])


# ---------------------------------------------------------------------------
# Integration tests: SSE stream emits images_generated event
# ---------------------------------------------------------------------------


async def test_sse_stream_emits_images_generated_event(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """images_generated event is emitted before order_complete."""
    compare_order = _make_img_order("img_sse1")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    result_order = _make_img_order("img_sse1")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = _cmp_df(25, 25)
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _text_block("I will compare these two logos visually."),
            _tool_use_block(
                name="generate_and_compare_images",
                tool_input={
                    "prompt_a": "Blue circular logo",
                    "prompt_b": "Red square logo",
                    "question": "Which logo is more memorable?",
                    "n": 50,
                },
                tool_id="tu_img_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                name="complete_research",
                tool_input={
                    "title": "Logo Preference Study",
                    "summary": "Both logos were equally preferred.",
                    "sections": [{"title": "Results", "content": "50/50 split."}],
                },
                tool_id="tu_complete",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Compare two logos")

    event_types = [e["event"] for e in events]
    assert "images_generated" in event_types
    assert "order_complete" in event_types
    assert "done" in event_types

    # images_generated must appear before order_complete
    img_idx = next(i for i, e in enumerate(events) if e["event"] == "images_generated")
    cmp_idx = next(i for i, e in enumerate(events) if e["event"] == "order_complete")
    assert img_idx < cmp_idx


async def test_images_generated_event_payload(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """images_generated SSE event carries all required fields with valid base64 images."""
    compare_order = _make_img_order("img_payload1")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    result_order = _make_img_order("img_payload1")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = _cmp_df(30, 20)
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                name="generate_and_compare_images",
                tool_input={
                    "prompt_a": "Prompt Alpha",
                    "prompt_b": "Prompt Beta",
                    "question": "Which is preferred?",
                    "n": 50,
                },
                tool_id="tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                name="complete_research",
                tool_input={
                    "title": "Preference Study",
                    "summary": "Alpha wins.",
                    "sections": [{"title": "Result", "content": "30 vs 20."}],
                },
                tool_id="tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Visual comparison")

    img_event = next(e for e in events if e["event"] == "images_generated")

    # Validate against the Pydantic model
    parsed = _SSEEventAdapter.validate_python(img_event)
    assert isinstance(parsed, ImagesGeneratedEvent)

    assert parsed.order_id == "img_payload1"
    assert parsed.prompt_a == "Prompt Alpha"
    assert parsed.prompt_b == "Prompt Beta"
    # Images must be non-empty valid base64
    assert len(parsed.image_a_b64) > 0
    assert len(parsed.image_b_b64) > 0
    base64.b64decode(parsed.image_a_b64)  # raises if not valid base64
    base64.b64decode(parsed.image_b_b64)


async def test_order_complete_follows_images_generated_with_distribution(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """order_complete after image A/B test carries vote distribution."""
    compare_order = _make_img_order("img_dist1")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    result_order = _make_img_order("img_dist1")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = _cmp_df(40, 10)
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                name="generate_and_compare_images",
                tool_input={
                    "prompt_a": "P_A",
                    "prompt_b": "P_B",
                    "question": "Q?",
                    "n": 50,
                },
                tool_id="tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                name="complete_research",
                tool_input={
                    "title": "T",
                    "summary": "A wins.",
                    "sections": [{"title": "R", "content": "40 vs 10."}],
                },
                tool_id="tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Image comparison")

    complete_event = next(e for e in events if e["event"] == "order_complete")
    parsed = _SSEEventAdapter.validate_python(complete_event)
    assert isinstance(parsed, OrderCompleteEvent)

    assert parsed.order_id == "img_dist1"
    assert parsed.distribution is not None
    assert parsed.distribution["option_a"] == 40
    assert parsed.distribution["option_b"] == 10
    assert parsed.winner == "option_a"
    assert parsed.n_responses == 50


# ---------------------------------------------------------------------------
# Test: image generation hard cap
# ---------------------------------------------------------------------------


async def test_image_generation_hard_cap_enforced(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """Agent respects MAX_IMAGE_GENERATIONS = 2; third call gets an error result."""
    from human_use.agent import MAX_IMAGE_GENERATIONS

    assert MAX_IMAGE_GENERATIONS == 2

    def _img_order(n: int) -> MagicMock:
        o = _make_img_order(f"img_cap_{n}")
        result_order = _make_img_order(f"img_cap_{n}")
        result_order.get_status.return_value = "Completed"
        result_order.get_results.return_value = _cmp_df(25, 25)
        return o, result_order

    o1, ro1 = _img_order(1)
    o2, ro2 = _img_order(2)
    mock_rapidata.order.create_compare_order.side_effect = [o1, o2]
    mock_rapidata.order.get_order_by_id.side_effect = [ro1, ro1, ro2, ro2]

    # Claude tries to dispatch 3 image generations — the third should be rejected
    resp1 = _claude_response(content=[
        _tool_use_block("generate_and_compare_images",
                        {"prompt_a": "A1", "prompt_b": "B1", "question": "Q1", "n": 50}, "t1"),
    ])
    resp2 = _claude_response(content=[
        _tool_use_block("generate_and_compare_images",
                        {"prompt_a": "A2", "prompt_b": "B2", "question": "Q2", "n": 50}, "t2"),
    ])
    resp3 = _claude_response(content=[
        _tool_use_block("generate_and_compare_images",
                        {"prompt_a": "A3", "prompt_b": "B3", "question": "Q3", "n": 50}, "t3"),
    ])
    resp4 = _claude_response(content=[
        _tool_use_block("complete_research",
                        {"title": "T", "summary": "Done.", "sections": []}, "t4"),
    ])

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp1, resp2, resp3, resp4])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Compare images")

    # Only 2 images_generated events should have been emitted
    img_events = [e for e in events if e["event"] == "images_generated"]
    assert len(img_events) == 2


# ---------------------------------------------------------------------------
# Test: done event messages include img:: tool_use/result pairs
# ---------------------------------------------------------------------------


async def test_done_messages_include_image_tool_use_and_result(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """done.messages must contain generate_and_compare_images tool_use + tool_result."""
    compare_order = _make_img_order("img_done1")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    result_order = _make_img_order("img_done1")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = _cmp_df(35, 15)
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "generate_and_compare_images",
                {"prompt_a": "PA", "prompt_b": "PB", "question": "Q", "n": 50},
                "tu_img",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"title": "T", "summary": "S.", "sections": [{"title": "R", "content": "C."}]},
                "tu_done",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Image A/B test")

    done_event = next(e for e in events if e["event"] == "done")
    messages = done_event["messages"]

    # Find an assistant message with generate_and_compare_images tool_use
    tool_use_found = any(
        isinstance(msg.get("content"), list)
        and any(
            block.get("type") == "tool_use"
            and block.get("name") == "generate_and_compare_images"
            for block in msg["content"]
        )
        for msg in messages
        if msg.get("role") == "assistant"
    )
    assert tool_use_found, "done.messages must contain generate_and_compare_images tool_use"

    # Find a corresponding tool_result in a user message
    tool_result_found = any(
        isinstance(msg.get("content"), list)
        and any(block.get("type") == "tool_result" for block in msg["content"])
        for msg in messages
        if msg.get("role") == "user"
    )
    assert tool_result_found, "done.messages must contain a tool_result for the image tool"


# ---------------------------------------------------------------------------
# Test: img:: no separate order_dispatched event
# ---------------------------------------------------------------------------


async def test_no_order_dispatched_event_for_image_orders(
    mock_rapidata: MagicMock,
    mock_genai: MagicMock,
) -> None:
    """Image orders must NOT emit order_dispatched — images_generated replaces it."""
    compare_order = _make_img_order("img_nodisp")
    mock_rapidata.order.create_compare_order.return_value = compare_order

    result_order = _make_img_order("img_nodisp")
    result_order.get_status.return_value = "Completed"
    result_order.get_results.return_value = _cmp_df(20, 30)
    mock_rapidata.order.get_order_by_id.return_value = result_order

    first_response = _claude_response(
        content=[
            _tool_use_block(
                "generate_and_compare_images",
                {"prompt_a": "P_A", "prompt_b": "P_B", "question": "Q?", "n": 50},
                "tu_1",
            ),
        ]
    )
    second_response = _claude_response(
        content=[
            _tool_use_block(
                "complete_research",
                {"title": "T", "summary": "B wins.", "sections": []},
                "tu_2",
            ),
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

    with patch("human_use.agent.anthropic.AsyncAnthropic", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            events = await _collect_events(client, "Compare images")

    # order_dispatched must NOT appear — only images_generated
    assert not any(e["event"] == "order_dispatched" for e in events)
    assert any(e["event"] == "images_generated" for e in events)


# ---------------------------------------------------------------------------
# Test: artifact persistence CRUD
# ---------------------------------------------------------------------------


async def test_save_and_get_image_artifact() -> None:
    """save_image_artifact / get_image_artifacts round-trip via in-memory SQLite."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    from human_use.crud import get_image_artifacts, save_image_artifact
    from human_use.db_models import ImageArtifact, Session, User  # noqa: F401 — registers tables

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as db:
        # Create user and session so FK constraints pass
        user_id = uuid.uuid4()
        from human_use.db_models import User as UserModel, Session as SessionModel
        from datetime import datetime

        user = UserModel(id=user_id, email="test@test.com", hashed_password="hash")
        db.add(user)
        await db.commit()

        session_id = uuid.uuid4()
        session = SessionModel(
            id=session_id,
            user_id=user_id,
            title="Test session",
            created_at=datetime.utcnow(),
        )
        db.add(session)
        await db.commit()

        # Save artifact
        artifact = await save_image_artifact(
            db,
            session_id=session_id,
            order_id="img::test_order",
            prompt_a="Blue logo",
            prompt_b="Red logo",
            image_a=FAKE_IMG_A,
            image_b=FAKE_IMG_B,
        )

        assert artifact.order_id == "img::test_order"
        assert artifact.prompt_a == "Blue logo"
        assert artifact.image_a == FAKE_IMG_A

        # Get artifacts (should return the one we just saved)
        artifacts = await get_image_artifacts(db, session_id, user_id)
        assert len(artifacts) == 1
        assert artifacts[0].order_id == "img::test_order"
        assert artifacts[0].image_b == FAKE_IMG_B

        # Get artifacts for wrong user returns empty
        other_user_id = uuid.uuid4()
        empty = await get_image_artifacts(db, session_id, other_user_id)
        assert empty == []

    await engine.dispose()


async def test_delete_session_cascades_to_image_artifacts() -> None:
    """delete_session must also remove associated ImageArtifact rows."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, select
    from sqlmodel.ext.asyncio.session import AsyncSession

    from human_use.crud import delete_session, save_image_artifact
    from human_use.db_models import ImageArtifact, Session, User  # noqa: F401
    from human_use.db_models import User as UserModel, Session as SessionModel
    from datetime import datetime

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as db:
        user_id = uuid.uuid4()
        user = UserModel(id=user_id, email="u@u.com", hashed_password="h")
        db.add(user)
        await db.commit()

        session_id = uuid.uuid4()
        session = SessionModel(
            id=session_id,
            user_id=user_id,
            title="S",
            created_at=datetime.utcnow(),
        )
        db.add(session)
        await db.commit()

        await save_image_artifact(
            db, session_id, "img::ord_del", "PA", "PB", FAKE_IMG_A, FAKE_IMG_B
        )

        deleted = await delete_session(db, session_id, user_id)
        assert deleted is True

        # Artifact must be gone
        result = await db.exec(select(ImageArtifact).where(ImageArtifact.session_id == session_id))
        assert result.all() == []

    await engine.dispose()
