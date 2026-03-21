from __future__ import annotations

import math

from rapidata import CountryFilter, LanguageFilter

from human_use.client import get_client, run_sync
from human_use.models import (
    CompareResult,
    FreeTextResult,
    MultipleChoiceResult,
    ProgressResult,
    RankedItem,
    RankResult,
    Result,
    TargetingConfig,
)

RESPONSES_PER_DATAPOINT = 10

# Map common language names the LLM might produce → ISO 639-1 two-letter codes.
# LanguageFilter validates that codes are exactly 2 characters.
_LANG_NAME_TO_CODE: dict[str, str] = {
    "afrikaans": "af", "albanian": "sq", "arabic": "ar", "armenian": "hy",
    "azerbaijani": "az", "basque": "eu", "belarusian": "be", "bengali": "bn",
    "bosnian": "bs", "bulgarian": "bg", "catalan": "ca", "chinese": "zh",
    "croatian": "hr", "czech": "cs", "danish": "da", "dutch": "nl",
    "english": "en", "estonian": "et", "finnish": "fi", "french": "fr",
    "galician": "gl", "georgian": "ka", "german": "de", "greek": "el",
    "gujarati": "gu", "hebrew": "he", "hindi": "hi", "hungarian": "hu",
    "icelandic": "is", "indonesian": "id", "irish": "ga", "italian": "it",
    "japanese": "ja", "kannada": "kn", "kazakh": "kk", "korean": "ko",
    "latvian": "lv", "lithuanian": "lt", "macedonian": "mk", "malay": "ms",
    "maltese": "mt", "norwegian": "no", "persian": "fa", "polish": "pl",
    "portuguese": "pt", "punjabi": "pa", "romanian": "ro", "russian": "ru",
    "serbian": "sr", "slovak": "sk", "slovenian": "sl", "spanish": "es",
    "swahili": "sw", "swedish": "sv", "tamil": "ta", "telugu": "te",
    "thai": "th", "turkish": "tr", "ukrainian": "uk", "urdu": "ur",
    "uzbek": "uz", "vietnamese": "vi", "welsh": "cy",
}


def _normalize_language(language: str) -> str:
    """Return a 2-letter ISO 639-1 code regardless of whether the agent
    passed a full name ('English') or a code ('en')."""
    if len(language) == 2:
        return language.lower()
    return _LANG_NAME_TO_CODE.get(language.lower(), language)


def _filters(language: str | None, targeting: TargetingConfig | None = None) -> list:
    filters: list = []
    if language:
        filters.append(LanguageFilter([_normalize_language(language)]))
    if targeting and targeting.country_codes:
        filters.append(CountryFilter(targeting.country_codes))
    return filters


def _n_datapoints(n: int) -> int:
    return max(1, math.ceil(n / RESPONSES_PER_DATAPOINT))


async def ask_free_text(question: str, n: int, language: str | None = None, targeting: TargetingConfig | None = None) -> str:
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
            filters=_filters(language, targeting),
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
    targeting: TargetingConfig | None = None,
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
            filters=_filters(language, targeting),
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
    targeting: TargetingConfig | None = None,
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
            filters=_filters(language, targeting),
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
    targeting: TargetingConfig | None = None,
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
            filters=_filters(language, targeting) or None,
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
            # Find the column most likely to contain free-text answers
            text_cols = [c for c in df.columns if any(k in str(c).lower() for k in ("response", "answer", "text", "result"))]
            col = text_cols[0] if text_cols else df.columns[-1]
            responses = df[col].dropna().tolist()
            # Flatten lists/dicts if needed
            flat: list[str] = []
            for r in responses:
                if isinstance(r, list):
                    flat.extend(str(x) for x in r if x is not None)
                else:
                    flat.append(str(r))
            return FreeTextResult(order_id=order_id, responses=flat, n_responses=len(flat))

        elif name.startswith("mc::"):
            agg_cols = [
                c for c in df.columns
                if c.startswith("aggregatedResults_")
                and not c.startswith("aggregatedResultsRatios_")
            ]
            counts: dict[str, int] = {
                col.replace("aggregatedResults_", ""): int(df[col].sum())
                for col in agg_cols
            }
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
            # _compare_to_pandas produces A_<metric> and B_<metric> columns
            a_cols = [c for c in df.columns if str(c).startswith("A_")]
            b_cols = [c for c in df.columns if str(c).startswith("B_")]
            if a_cols and b_cols:
                a_votes = int(df[a_cols[0]].sum())
                b_votes = int(df[b_cols[0]].sum())
            else:
                # Fallback: last two numeric columns
                num_cols = df.select_dtypes("number").columns.tolist()
                a_votes = int(df[num_cols[-2]].sum()) if len(num_cols) >= 2 else 0
                b_votes = int(df[num_cols[-1]].sum()) if len(num_cols) >= 1 else 0
            asset_a = str(df["assetA"].iloc[0]) if "assetA" in df.columns else "option_a"
            asset_b = str(df["assetB"].iloc[0]) if "assetB" in df.columns else "option_b"
            total = a_votes + b_votes
            winner_text = asset_a if a_votes >= b_votes else asset_b
            winner = "option_a" if a_votes >= b_votes else "option_b"
            return CompareResult(
                order_id=order_id,
                winner=winner,
                winner_text=winner_text,
                option_a_votes=a_votes,
                option_b_votes=b_votes,
                confidence=max(a_votes, b_votes) / total if total else 0.0,
                n_responses=total,
            )

        else:  # rnk::
            # _compare_to_pandas() only handles 2 assets; parse raw dict directly.
            # Each result item has aggregatedResults: {item_name: elo_score, ...}
            scores: dict[str, float] = {}
            total_votes = 0
            for result_item in raw.get("results", []):
                agg = result_item.get("aggregatedResults", {})
                if isinstance(agg, dict):
                    for item_name, score in agg.items():
                        try:
                            scores[str(item_name)] = float(score)
                        except (TypeError, ValueError):
                            pass
                votes = result_item.get("totalVotes") or result_item.get("votes", 0)
                try:
                    total_votes += int(votes)
                except (TypeError, ValueError):
                    pass

            if not scores:
                # Fallback: try the DataFrame heuristic
                score_cols = [c for c in df.columns if "score" in str(c).lower() or "elo" in str(c).lower()]
                item_cols = [c for c in df.columns if "item" in str(c).lower() or "text" in str(c).lower() or "asset" in str(c).lower()]
                sort_col = score_cols[0] if score_cols else df.columns[-1]
                item_col = item_cols[0] if item_cols else df.columns[0]
                sorted_df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
                rankings = [
                    RankedItem(item=str(row[item_col]), rank=i + 1, score=float(row[sort_col]))
                    for i, row in sorted_df.iterrows()
                ]
                return RankResult(order_id=order_id, rankings=rankings, n_responses=len(df))

            sorted_items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            rankings = [
                RankedItem(item=item, rank=i + 1, score=score)
                for i, (item, score) in enumerate(sorted_items)
            ]
            return RankResult(
                order_id=order_id,
                rankings=rankings,
                n_responses=total_votes or len(rankings),
            )

    return await run_sync(_fetch)  # type: ignore[return-value]


async def ask_clarifying_question(question: str, options: list[str]) -> str:
    """
    Ask the user a clarifying multiple-choice question before dispatching surveys.

    Use this at most 3 times to understand the research goal before dispatching any
    Rapidata orders. Ask clarifying questions first, then proceed to surveys.

    The tool automatically appends "Other (please specify)" as a fourth option, so
    pass exactly 3 options.

    Args:
        question: The clarifying question to ask the user.
        options: Exactly 3 answer options to present.

    Returns:
        The user's selected answer as a string.

    Note: This tool requires the interactive web frontend (/research/stream endpoint).
    """
    raise NotImplementedError(
        "ask_clarifying_question requires the interactive web frontend. "
        "Use the /research/stream endpoint with a session_id."
    )


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
