from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette import EventSourceResponse, ServerSentEvent

from human_use.agent import run_agent
from human_use.models import SSEEvent, TargetingConfig

app = FastAPI(title="human-use research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class AnswerRequest(BaseModel):
    session_id: str
    question_index: int
    answer: str


@app.post("/research/stream")
async def research_stream(
    body: ResearchRequest,
    country_codes: list[str] = Query(default=[]),
) -> EventSourceResponse:
    question = body.question
    session_id = body.session_id
    targeting = TargetingConfig(country_codes=country_codes) if country_codes else None
    queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()

    async def answer_awaiter(question_index: int) -> str:
        return await _await_answer(session_id, question_index)

    async def generate() -> AsyncIterator[ServerSentEvent]:
        task = asyncio.create_task(
            run_agent(question, queue, session_id=session_id, answer_awaiter=answer_awaiter, targeting=targeting)
        )
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
