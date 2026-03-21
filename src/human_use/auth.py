from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel.ext.asyncio.session import AsyncSession

from human_use.db import get_session
from human_use.db_models import User

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY: str = os.environ.get("JWT_SECRET", "dev-secret-change-me")
ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))

_bearer = HTTPBearer(auto_error=False)

# ── Password helpers ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ───────────────────────────────────────────────────────────────


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise ValueError("no sub")
        return uuid.UUID(sub)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── FastAPI dependencies ──────────────────────────────────────────────────────


async def _resolve_user(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
) -> User:
    user_id = _decode_token(credentials.credentials)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await _resolve_user(credentials, db)


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User | None:
    if credentials is None:
        return None
    try:
        return await _resolve_user(credentials, db)
    except HTTPException:
        return None
