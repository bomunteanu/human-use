from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
