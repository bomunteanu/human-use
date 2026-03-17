from __future__ import annotations

import math

from rapidata import LanguageFilter

from human_use.client import get_client, run_sync
from human_use.models import (
    CompareResult,
    FreeTextResult,
    MultipleChoiceResult,
    ProgressResult,
    RankedItem,
    RankResult,
    Result,
)

RESPONSES_PER_DATAPOINT = 10


def _filters(language: str | None) -> list:
    return [LanguageFilter([language])] if language else []


def _n_datapoints(n: int) -> int:
    return max(1, math.ceil(n / RESPONSES_PER_DATAPOINT))


async def ask_free_text(question: str, n: int, language: str | None = None) -> str:
    """
    Dispatch a free-text question to real humans and return an order_id immediately.

    Use this when you need open-ended qualitative responses — opinions, descriptions,
    creative answers, or anything that cannot be captured by a fixed set of options.
    Collect n human responses (rounded up to the nearest 10).

    After calling this, use check_progress(order_id) to poll for completion, then
    get_results(order_id) to retrieve a FreeTextResult with all responses.

    Args:
        question: The question to ask humans.
        n: Total number of human responses to collect.
        language: ISO 639-1 language code to restrict annotators (e.g. "en", "fr").
                  Omit to allow all languages.

    Returns:
        order_id to use with check_progress and get_results.
    """
    client = get_client()
    datapoints = [question] * _n_datapoints(n)

    def _create() -> str:
        order = client.order.create_free_text_order(
            name=f"ft::{question[:80]}",
            instruction=question,
            datapoints=datapoints,
            responses_per_datapoint=RESPONSES_PER_DATAPOINT,
            filters=_filters(language),
            data_type="text",
        )
        order.run()
        return order.id

    return await run_sync(_create)


async def ask_multiple_choice(
    question: str,
    options: list[str],
    n: int,
    language: str | None = None,
) -> str:
    """
    Dispatch a multiple-choice poll to real humans and return an order_id immediately.

    Use this when you need humans to select from a known set of options — to gauge
    preference, categorize content, or collect a vote. Best when options are exhaustive
    and mutually exclusive.

    After calling this, use check_progress(order_id) to poll for completion, then
    get_results(order_id) to retrieve a MultipleChoiceResult with winner, distribution,
    and confidence.

    Args:
        question: The question or instruction shown to annotators.
        options: The list of answer choices (2–10 recommended).
        n: Total number of human responses to collect.
        language: ISO 639-1 language code to restrict annotators. Omit for all languages.

    Returns:
        order_id to use with check_progress and get_results.
    """
    client = get_client()
    datapoints = [question] * _n_datapoints(n)

    def _create() -> str:
        order = client.order.create_classification_order(
            name=f"mc::{question[:80]}",
            instruction=question,
            answer_options=options,
            datapoints=datapoints,
            responses_per_datapoint=RESPONSES_PER_DATAPOINT,
            filters=_filters(language),
            data_type="text",
        )
        order.run()
        return order.id

    return await run_sync(_create)


async def compare(
    question: str,
    option_a: str,
    option_b: str,
    n: int,
    language: str | None = None,
) -> str:
    """
    Dispatch a pairwise comparison to real humans and return an order_id immediately.

    Use this when you need a human preference judgment between exactly two candidates —
    two generated texts, model outputs, headlines, or any binary choice. More reliable
    than multiple-choice for nuanced preference tasks.

    After calling this, use check_progress(order_id) to poll for completion, then
    get_results(order_id) to retrieve a CompareResult with winner, vote counts,
    and confidence.

    Args:
        question: The comparison question or instruction (e.g. "Which is more helpful?").
        option_a: First option shown to annotators.
        option_b: Second option shown to annotators.
        n: Total number of human judgments to collect.
        language: ISO 639-1 language code to restrict annotators. Omit for all languages.

    Returns:
        order_id to use with check_progress and get_results.
    """
    client = get_client()
    n_dp = _n_datapoints(n)
    datapoints = [[option_a, option_b]] * n_dp

    def _create() -> str:
        order = client.order.create_compare_order(
            name=f"cmp::{question[:80]}",
            instruction=question,
            datapoints=datapoints,
            responses_per_datapoint=RESPONSES_PER_DATAPOINT,
            filters=_filters(language),
            data_type="text",
        )
        order.run()
        return order.id

    return await run_sync(_create)


async def rank(
    question: str,
    items: list[str],
    n: int,
    language: str | None = None,
) -> str:
    """
    Dispatch a ranking task to real humans and return an order_id immediately.

    Use this when you need a full ordered ranking of multiple candidates — not just
    a winner. Humans perform pairwise comparisons internally to produce a ranked list.
    Increase n for a more statistically reliable ranking (n is the comparison budget).

    After calling this, use check_progress(order_id) to poll for completion, then
    get_results(order_id) to retrieve a RankResult with items sorted by human preference.

    Args:
        question: The ranking question (e.g. "Which is most helpful?").
        items: The list of items to rank (2 or more).
        n: Comparison budget — total pairwise comparisons to run. Higher = more accurate.
        language: ISO 639-1 language code to restrict annotators. Omit for all languages.

    Returns:
        order_id to use with check_progress and get_results.
    """
    client = get_client()

    def _create() -> str:
        order = client.order.create_ranking_order(
            name=f"rnk::{question[:80]}",
            instruction=question,
            datapoints=[items],
            comparison_budget_per_ranking=n,
            data_type="text",
        )
        order.run()
        return order.id

    return await run_sync(_create)


async def get_results(order_id: str) -> Result:
    """
    Retrieve completed human responses for a dispatched order.

    Use this after check_progress confirms is_complete is True. Returns a typed result
    matching the original order:
    - FreeTextResult: list of open-ended text responses
    - MultipleChoiceResult: winner, per-option vote distribution, and confidence
    - CompareResult: winner (option_a or option_b), vote counts, and confidence
    - RankResult: items ranked from first to last with scores

    Args:
        order_id: The order_id returned by ask_free_text, ask_multiple_choice,
                  compare, or rank.

    Returns:
        A typed result model. Check order_type field to discriminate the union.
    """
    client = get_client()

    def _fetch() -> Result:
        order = client.order.get_order_by_id(order_id)
        raw = order.get_results()
        df = raw.to_pandas()
        name: str = order.name

        if name.startswith("ft::"):
            responses = df.iloc[:, -1].dropna().tolist()
            return FreeTextResult(
                order_id=order_id,
                responses=[str(r) for r in responses],
                n_responses=len(responses),
            )

        elif name.startswith("mc::"):
            counts: dict[str, int] = df.iloc[:, -1].value_counts().to_dict()
            total = sum(counts.values())
            winner = max(counts, key=lambda k: counts[k])
            return MultipleChoiceResult(
                order_id=order_id,
                winner=winner,
                distribution=counts,
                confidence=counts[winner] / total if total else 0.0,
                n_responses=total,
            )

        elif name.startswith("cmp::"):
            a_votes = int(df.iloc[:, -2].sum())
            b_votes = int(df.iloc[:, -1].sum())
            total = a_votes + b_votes
            if a_votes >= b_votes:
                winner = "option_a"
            else:
                winner = "option_b"
            return CompareResult(
                order_id=order_id,
                winner=winner,
                winner_text=name.split("::", 1)[-1],
                option_a_votes=a_votes,
                option_b_votes=b_votes,
                confidence=max(a_votes, b_votes) / total if total else 0.0,
                n_responses=total,
            )

        else:  # rnk::
            score_cols = [c for c in df.columns if "score" in str(c).lower()]
            item_cols = [
                c
                for c in df.columns
                if "item" in str(c).lower() or "datapoint" in str(c).lower()
            ]
            sort_col = score_cols[0] if score_cols else df.columns[-1]
            item_col = item_cols[0] if item_cols else df.columns[0]
            sorted_df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
            rankings = [
                RankedItem(
                    item=str(row[item_col]),
                    rank=i + 1,
                    score=float(row[sort_col]),
                )
                for i, row in sorted_df.iterrows()
            ]
            return RankResult(
                order_id=order_id,
                rankings=rankings,
                n_responses=len(df),
            )

    return await run_sync(_fetch)  # type: ignore[return-value]


async def check_progress(order_id: str) -> ProgressResult:
    """
    Check whether a dispatched human intelligence order has completed.

    Use this to poll order status before calling get_results. When is_complete
    is True, the order is done and get_results(order_id) will return full results.
    Poll periodically (e.g. every 30 seconds) rather than in a tight loop.

    Args:
        order_id: The order_id returned by any dispatch tool.

    Returns:
        ProgressResult with status string and is_complete boolean.
        status values: Created | Submitted | Processing | Completed | Failed
    """
    client = get_client()

    def _check() -> ProgressResult:
        order = client.order.get_order_by_id(order_id)
        status: str = order.get_status()
        return ProgressResult(
            order_id=order_id,
            status=status,
            is_complete=status == "Completed",
        )

    return await run_sync(_check)
