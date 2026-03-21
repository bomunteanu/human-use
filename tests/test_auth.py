"""Tests for /auth/register and /auth/login endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def test_register_success(client: AsyncClient):
    res = await client.post(
        "/auth/register", json={"email": "user@test.com", "password": "password1"}
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@test.com", "password": "password1"}
    await client.post("/auth/register", json=payload)
    res = await client.post("/auth/register", json=payload)
    assert res.status_code == 409
    assert res.json()["detail"] == "Email already registered"


async def test_register_password_too_short(client: AsyncClient):
    res = await client.post(
        "/auth/register", json={"email": "short@test.com", "password": "abc"}
    )
    assert res.status_code == 422


async def test_register_invalid_email(client: AsyncClient):
    res = await client.post(
        "/auth/register", json={"email": "not-an-email", "password": "password1"}
    )
    assert res.status_code == 422


async def test_login_success(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "login@test.com", "password": "password1"}
    )
    res = await client.post(
        "/auth/login", json={"email": "login@test.com", "password": "password1"}
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "wrong@test.com", "password": "password1"}
    )
    res = await client.post(
        "/auth/login", json={"email": "wrong@test.com", "password": "wrongpass"}
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


async def test_login_nonexistent_user(client: AsyncClient):
    res = await client.post(
        "/auth/login", json={"email": "nobody@test.com", "password": "password1"}
    )
    assert res.status_code == 401


async def test_protected_route_without_token(client: AsyncClient):
    res = await client.get("/sessions")
    assert res.status_code == 401


async def test_protected_route_with_invalid_token(client: AsyncClient):
    res = await client.get(
        "/sessions", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert res.status_code == 401
