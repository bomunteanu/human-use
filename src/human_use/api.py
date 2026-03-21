from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette import EventSourceResponse, ServerSentEvent

from human_use.agent import run_agent
from human_use.models import SSEEvent

app = FastAPI(title="human-use research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    question: str


@app.post("/research/stream")
async def research_stream(body: ResearchRequest) -> EventSourceResponse:
    question = body.question
    queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()

    async def generate() -> AsyncIterator[ServerSentEvent]:
        task = asyncio.create_task(run_agent(question, queue))
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
