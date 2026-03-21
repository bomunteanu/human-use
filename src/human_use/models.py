from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class FreeTextResult(BaseModel):
    order_id: str
    order_type: Literal["free_text"] = "free_text"
    responses: list[str]
    n_responses: int


class MultipleChoiceResult(BaseModel):
    order_id: str
    order_type: Literal["multiple_choice"] = "multiple_choice"
    winner: str
    distribution: dict[str, int]
    confidence: float
    n_responses: int


class CompareResult(BaseModel):
    order_id: str
    order_type: Literal["compare"] = "compare"
    winner: str
    winner_text: str
    option_a_votes: int
    option_b_votes: int
    confidence: float
    n_responses: int


class RankedItem(BaseModel):
    item: str
    rank: int
    score: float


class RankResult(BaseModel):
    order_id: str
    order_type: Literal["rank"] = "rank"
    rankings: list[RankedItem]
    n_responses: int


class ProgressResult(BaseModel):
    order_id: str
    status: str
    is_complete: bool


Result = FreeTextResult | MultipleChoiceResult | CompareResult | RankResult


# ---------------------------------------------------------------------------
# SSE event models
# ---------------------------------------------------------------------------


class AgentThoughtEvent(BaseModel):
    event: Literal["agent_thought"] = "agent_thought"
    text: str


class OrderDispatchedEvent(BaseModel):
    event: Literal["order_dispatched"] = "order_dispatched"
    order_id: str
    tool: str
    question: str


class OrderProgressEvent(BaseModel):
    event: Literal["order_progress"] = "order_progress"
    order_id: str
    status: str
    is_complete: bool


class OrderCompleteEvent(BaseModel):
    event: Literal["order_complete"] = "order_complete"
    order_id: str
    distribution: dict[str, int] | None = None
    winner: str | None = None
    n_responses: int


class BriefSection(BaseModel):
    title: str
    content: str


class BriefUpdateEvent(BaseModel):
    event: Literal["brief_update"] = "brief_update"
    section: BriefSection


class ResearchBrief(BaseModel):
    question: str
    sections: list[BriefSection]
    summary: str


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    brief: ResearchBrief


SSEEvent = Annotated[
    AgentThoughtEvent
    | OrderDispatchedEvent
    | OrderProgressEvent
    | OrderCompleteEvent
    | BriefUpdateEvent
    | DoneEvent,
    Field(discriminator="event"),
]
