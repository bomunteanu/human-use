from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from human_use.auth import get_current_user
from human_use.crud import delete_session, get_session_with_messages, get_sessions
from human_use.db import get_session as get_db
from human_use.db_models import User

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str
    brief: Any | None = None  # ResearchBrief JSON — present when session is complete


class SessionDetail(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str
    brief: Any | None = None
    messages: list[dict]


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SessionSummary]:
    sessions = await get_sessions(db, current_user.id)
    return [
        SessionSummary(
            id=s.id,
            title=s.title,
            created_at=s.created_at.isoformat(),
            brief=s.brief,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionDetail:
    result = await get_session_with_messages(db, session_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    session, messages = result
    return SessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat(),
        brief=session.brief,
        messages=[{"role": m.role, "content": m.content} for m in messages],
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session_endpoint(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    deleted = await delete_session(db, session_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
