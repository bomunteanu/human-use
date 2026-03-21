"""Tests for /sessions CRUD endpoints."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from human_use.crud import get_user_by_email, save_messages, upsert_session


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str = "u@test.com", password: str = "password1") -> str:
    res = await client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Tests ────────────────────────────────────────────────────────────────────


async def test_list_sessions_empty(client: AsyncClient):
    token = await _register(client)
    res = await client.get("/sessions", headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == []


async def test_list_sessions_only_own(client: AsyncClient, db_session: AsyncSession):
    token_a = await _register(client, "a@test.com")
    token_b = await _register(client, "b@test.com")

    user_a = await get_user_by_email(db_session, "a@test.com")
    assert user_a is not None
    sid = uuid.uuid4()
    await upsert_session(db_session, sid, user_a.id, "User A session")

    # B should see nothing
    res_b = await client.get("/sessions", headers=_auth(token_b))
    assert res_b.json() == []

    # A sees their session
    res_a = await client.get("/sessions", headers=_auth(token_a))
    assert len(res_a.json()) == 1
    assert res_a.json()[0]["title"] == "User A session"


async def test_get_session_with_messages(client: AsyncClient, db_session: AsyncSession):
    token = await _register(client)
    user = await get_user_by_email(db_session, "u@test.com")
    assert user is not None
    sid = uuid.uuid4()
    await upsert_session(db_session, sid, user.id, "Test session")

    msgs = [
        {"role": "user", "content": "Research question: what do people think?"},
        {"role": "assistant", "content": [{"type": "text", "text": "Thinking..."}]},
    ]
    await save_messages(db_session, sid, msgs)

    res = await client.get(f"/sessions/{sid}", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Test session"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


async def test_get_session_wrong_user(client: AsyncClient, db_session: AsyncSession):
    token_a = await _register(client, "a2@test.com")
    token_b = await _register(client, "b2@test.com")

    user_a = await get_user_by_email(db_session, "a2@test.com")
    assert user_a is not None
    sid = uuid.uuid4()
    await upsert_session(db_session, sid, user_a.id, "Private")

    # B cannot read A's session
    res = await client.get(f"/sessions/{sid}", headers=_auth(token_b))
    assert res.status_code == 404


async def test_get_session_not_found(client: AsyncClient):
    token = await _register(client)
    res = await client.get(f"/sessions/{uuid.uuid4()}", headers=_auth(token))
    assert res.status_code == 404


async def test_delete_session(client: AsyncClient, db_session: AsyncSession):
    token = await _register(client)
    user = await get_user_by_email(db_session, "u@test.com")
    assert user is not None
    sid = uuid.uuid4()
    await upsert_session(db_session, sid, user.id, "To delete")

    res = await client.delete(f"/sessions/{sid}", headers=_auth(token))
    assert res.status_code == 204

    res2 = await client.get(f"/sessions/{sid}", headers=_auth(token))
    assert res2.status_code == 404


async def test_delete_session_wrong_user(client: AsyncClient, db_session: AsyncSession):
    token_a = await _register(client, "a3@test.com")
    token_b = await _register(client, "b3@test.com")

    user_a = await get_user_by_email(db_session, "a3@test.com")
    assert user_a is not None
    sid = uuid.uuid4()
    await upsert_session(db_session, sid, user_a.id, "A's session")

    res = await client.delete(f"/sessions/{sid}", headers=_auth(token_b))
    assert res.status_code == 404


async def test_title_truncated_to_60(client: AsyncClient, db_session: AsyncSession):
    token = await _register(client)
    user = await get_user_by_email(db_session, "u@test.com")
    assert user is not None
    sid = uuid.uuid4()
    long_title = "A" * 100
    await upsert_session(db_session, sid, user.id, long_title)

    res = await client.get(f"/sessions/{sid}", headers=_auth(token))
    assert len(res.json()["title"]) == 60


async def test_upsert_session_noop_on_second_call(db_session: AsyncSession):
    user_id = uuid.uuid4()
    sid = uuid.uuid4()

    # Need a real user row first (FK constraint)
    from human_use.crud import create_user
    from human_use.auth import hash_password
    user = await create_user(db_session, "noop@test.com", hash_password("password1"))

    s1 = await upsert_session(db_session, sid, user.id, "First title")
    s2 = await upsert_session(db_session, sid, user.id, "Second title")

    # Title should be unchanged (no update on second call)
    assert s2.title == "First title"
    assert s1.id == s2.id


async def test_messages_order_preserved(client: AsyncClient, db_session: AsyncSession):
    token = await _register(client)
    user = await get_user_by_email(db_session, "u@test.com")
    assert user is not None
    sid = uuid.uuid4()
    await upsert_session(db_session, sid, user.id, "Order test")

    msgs = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    await save_messages(db_session, sid, msgs)

    res = await client.get(f"/sessions/{sid}", headers=_auth(token))
    returned = res.json()["messages"]
    assert [m["content"] for m in returned] == ["first", "second", "third"]
