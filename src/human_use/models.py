from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class AgeGroup(str, Enum):
    UNDER_18 = "under_18"
    AGE_18_24 = "18-24"
    AGE_25_34 = "25-34"
    AGE_35_44 = "35-44"
    AGE_45_54 = "45-54"
    AGE_55_PLUS = "55+"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class TargetingConfig(BaseModel):
    """Full demographic targeting for Rapidata orders. All empty = Worldwide / all demographics."""

    country_codes: list[str] = []  # ISO 3166-1 alpha-2; empty = no filter
    languages: list[str] = []      # ISO 639-1; empty = all languages
    age_groups: list[AgeGroup] = []  # empty = all ages
    genders: list[Gender] = []       # empty = all genders


class FreeTextResult(BaseModel):
    order_id: str
    order_type: Literal["free_text"] = "free_text"
    responses: list[str]
    n_responses: int
    country_counts: dict[str, int] = Field(default_factory=dict)


class MultipleChoiceResult(BaseModel):
    order_id: str
    order_type: Literal["multiple_choice"] = "multiple_choice"
    winner: str
    distribution: dict[str, int]
    confidence: float
    n_responses: int
    country_counts: dict[str, int] = Field(default_factory=dict)


class CompareResult(BaseModel):
    order_id: str
    order_type: Literal["compare"] = "compare"
    winner: str
    winner_text: str
    option_a_votes: int
    option_b_votes: int
    confidence: float
    n_responses: int
    country_counts: dict[str, int] = Field(default_factory=dict)


class RankedItem(BaseModel):
    item: str
    rank: int
    score: float


class RankResult(BaseModel):
    order_id: str
    order_type: Literal["rank"] = "rank"
    rankings: list[RankedItem]
    n_responses: int
    country_counts: dict[str, int] = Field(default_factory=dict)


class ProgressResult(BaseModel):
    order_id: str
    status: str
    is_complete: bool


Result = FreeTextResult | MultipleChoiceResult | CompareResult | RankResult


# ---------------------------------------------------------------------------
# SSE event models
# ---------------------------------------------------------------------------


class ClarifyingQuestionEvent(BaseModel):
    event: Literal["clarifying_question"] = "clarifying_question"
    session_id: str
    question_index: int
    question: str
    options: list[str]  # always 4 items: 3 provided + "Other (please specify)"


class AgentThoughtEvent(BaseModel):
    event: Literal["agent_thought"] = "agent_thought"
    text: str


class TargetingUpdateEvent(BaseModel):
    event: Literal["targeting_update"] = "targeting_update"
    country_codes: list[str]
    languages: list[str]
    age_groups: list[str]
    genders: list[str]


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
    country_counts: dict[str, int] = Field(default_factory=dict)


class OrderPartialResultsEvent(BaseModel):
    """Preliminary results while the order is still collecting responses."""
    event: Literal["order_partial_results"] = "order_partial_results"
    order_id: str
    distribution: dict[str, int] | None = None
    winner: str | None = None
    n_responses: int
    country_counts: dict[str, int] = Field(default_factory=dict)


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
    title: str = ""


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    brief: ResearchBrief
    messages: list[dict[str, object]] = Field(default_factory=list)


SSEEvent = Annotated[
    ClarifyingQuestionEvent
    | AgentThoughtEvent
    | TargetingUpdateEvent
    | OrderDispatchedEvent
    | OrderProgressEvent
    | OrderCompleteEvent
    | OrderPartialResultsEvent
    | BriefUpdateEvent
    | DoneEvent,
    Field(discriminator="event"),
]
