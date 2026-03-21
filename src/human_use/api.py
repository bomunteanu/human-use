from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse, ServerSentEvent
from sqlmodel.ext.asyncio.session import AsyncSession

from human_use.agent import run_agent, run_compile
from human_use.auth import get_optional_user
from human_use.crud import save_messages, upsert_session
from human_use.db import create_db_and_tables, get_session
from human_use.db_models import User
from human_use.models import SSEEvent, TargetingConfig
from human_use.routers.auth import router as auth_router
from human_use.routers.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(title="human-use research API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sessions_router)

# Keyed by (session_id, question_index)
_pending_events: dict[tuple[str, int], asyncio.Event] = {}
_pending_answers: dict[tuple[str, int], str] = {}


async def _await_answer(session_id: str, question_index: int) -> str:
    key = (session_id, question_index)
    ev = asyncio.Event()
    _pending_events[key] = ev
    # Race: answer may have arrived before we registered the event
    if key in _pending_answers:
        del _pending_events[key]
        return _pending_answers.pop(key)
    await ev.wait()
    _pending_events.pop(key, None)
    return _pending_answers.pop(key)


def _cleanup_session(session_id: str) -> None:
    stale = [k for k in _pending_events if k[0] == session_id]
    for k in stale:
        ev = _pending_events.pop(k, None)
        if ev:
            ev.set()  # unblock any waiting coroutine so it can exit
    stale2 = [k for k in _pending_answers if k[0] == session_id]
    for k in stale2:
        _pending_answers.pop(k, None)


class ResearchRequest(BaseModel):
    question: str
    session_id: str
    messages: list[dict[str, object]] = Field(default_factory=list)
    targeting: TargetingConfig | None = None


class AnswerRequest(BaseModel):
    session_id: str
    question_index: int
    answer: str


class CompileRequest(BaseModel):
    session_id: str
    messages: list[dict[str, object]]


@app.post("/research/stream")
async def research_stream(
    body: ResearchRequest,
    current_user: Annotated[User | None, Depends(get_optional_user)] = None,
    db: Annotated[AsyncSession, Depends(get_session)] = None,
) -> EventSourceResponse:
    question = body.question
    session_id = body.session_id
    # Use targeting from body; None means use defaults (all-empty = Worldwide)
    targeting = body.targeting if body.targeting is not None else None
    queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()

    async def answer_awaiter(question_index: int) -> str:
        return await _await_answer(session_id, question_index)

    async def generate() -> AsyncIterator[ServerSentEvent]:
        task = asyncio.create_task(
            run_agent(
                question,
                queue,
                session_id=session_id,
                answer_awaiter=answer_awaiter,
                targeting=targeting,
                prior_messages=body.messages if body.messages else None,
            )
        )
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                # Persist session on done if authenticated
                if event.event == "done" and current_user is not None and db is not None:
                    session_uuid = uuid.UUID(session_id)
                    await upsert_session(
                        db,
                        session_uuid,
                        current_user.id,
                        question[:60],
                        brief=event.brief.model_dump(),
                    )
                    await save_messages(db, session_uuid, event.messages)
                yield ServerSentEvent(
                    data=event.model_dump_json(),
                    event=event.event,
                )
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            _cleanup_session(session_id)

    return EventSourceResponse(generate())


@app.post("/research/answer")
async def research_answer(body: AnswerRequest) -> dict[str, bool]:
    key = (body.session_id, body.question_index)
    _pending_answers[key] = body.answer
    ev = _pending_events.get(key)
    if ev:
        ev.set()
    return {"ok": True}


@app.post("/research/compile")
async def research_compile(body: CompileRequest) -> EventSourceResponse:
    queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()

    async def generate() -> AsyncIterator[ServerSentEvent]:
        task = asyncio.create_task(run_compile(body.messages, queue))
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield ServerSentEvent(
                    data=event.model_dump_json(),
                    event=event.event,
                )
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return EventSourceResponse(generate())
