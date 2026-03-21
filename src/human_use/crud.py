from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from human_use.db_models import Message, Session, User


# ── User ──────────────────────────────────────────────────────────────────────


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.exec(select(User).where(User.email == email))
    return result.first()


async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
) -> User:
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── Session ───────────────────────────────────────────────────────────────────


async def upsert_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    brief: dict | None = None,
) -> Session:
    """Create session if it doesn't exist. Always updates brief when provided."""
    existing = await db.get(Session, session_id)
    if existing is not None:
        if brief is not None:
            existing.brief = brief
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
        return existing
    session = Session(id=session_id, user_id=user_id, title=title[:60], brief=brief)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def save_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    anthropic_messages: list[dict],
) -> None:
    """Replace all messages for this session with the complete history."""
    existing = await db.exec(
        select(Message).where(Message.session_id == session_id)
    )
    for msg in existing.all():
        await db.delete(msg)

    for idx, msg in enumerate(anthropic_messages):
        row = Message(
            session_id=session_id,
            role=msg["role"],
            content=msg["content"],
            order_index=idx,
        )
        db.add(row)

    await db.commit()


async def get_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[Session]:
    """Return all sessions for a user, newest first."""
    result = await db.exec(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.created_at.desc())
    )
    return list(result.all())


async def get_session_with_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[Session, list[Message]] | None:
    session = await db.get(Session, session_id)
    if session is None or session.user_id != user_id:
        return None
    result = await db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.order_index.asc())
    )
    return session, list(result.all())


async def rename_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
) -> bool:
    session = await db.get(Session, session_id)
    if session is None or session.user_id != user_id:
        return False
    session.title = title[:60]
    db.add(session)
    await db.commit()
    return True


async def delete_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    session = await db.get(Session, session_id)
    if session is None or session.user_id != user_id:
        return False
    msgs = await db.exec(
        select(Message).where(Message.session_id == session_id)
    )
    for msg in msgs.all():
        await db.delete(msg)
    await db.delete(session)
    await db.commit()
    return True
