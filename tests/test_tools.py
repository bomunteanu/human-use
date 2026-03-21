"""
Tests for human_use tools.

All tests mock RapidataClient entirely — no real API calls are made.
Each test verifies:
  - The correct SDK method is called
  - The correct arguments are passed (including hardcoded responses_per_datapoint=10)
  - Language filter is applied when provided and absent when not
  - Results are correctly parsed into typed Pydantic models
"""

import asyncio
from unittest.mock import MagicMock

import pandas as pd
import pytest

import human_use.client as client_module
from human_use import tools
from human_use.models import (
    CompareResult,
    FreeTextResult,
    MultipleChoiceResult,
    ProgressResult,
    RankResult,
)

RESPONSES_PER_DATAPOINT = 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the lazy singleton between tests."""
    client_module._client = None
    yield
    client_module._client = None


@pytest.fixture
def mock_rapidata(monkeypatch):
    """Inject a fully mocked RapidataClient into the client module."""
    mock = MagicMock()
    monkeypatch.setattr("human_use.client.RapidataClient", lambda **kw: mock)
    monkeypatch.setenv("RAPIDATA_CLIENT_ID", "test_id")
    monkeypatch.setenv("RAPIDATA_CLIENT_SECRET", "test_secret")
    return mock


def make_order(name: str, order_id: str = "ord_123") -> MagicMock:
    order = MagicMock()
    order.id = order_id
    order.name = name
    order.run.return_value = order
    return order


# ---------------------------------------------------------------------------
# ask_multiple_choice
# ---------------------------------------------------------------------------


def test_ask_multiple_choice_returns_order_id(mock_rapidata):
    order = make_order("mc::Q")
    mock_rapidata.order.create_classification_order.return_value = order

    result = asyncio.run(tools.ask_multiple_choice("Q", ["A", "B", "C"], n=10))

    assert result == "ord_123"


def test_ask_multiple_choice_calls_correct_sdk_method(mock_rapidata):
    order = make_order("mc::Q")
    mock_rapidata.order.create_classification_order.return_value = order

    asyncio.run(tools.ask_multiple_choice("Q", ["A", "B"], n=10))

    mock_rapidata.order.create_classification_order.assert_called_once()


def test_ask_multiple_choice_passes_options(mock_rapidata):
    order = make_order("mc::Q")
    mock_rapidata.order.create_classification_order.return_value = order

    asyncio.run(tools.ask_multiple_choice("Q", ["yes", "no", "maybe"], n=10))

    _, kwargs = mock_rapidata.order.create_classification_order.call_args
    assert kwargs["answer_options"] == ["yes", "no", "maybe"]


def test_ask_multiple_choice_hardcodes_responses_per_datapoint(mock_rapidata):
    order = make_order("mc::Q")
    mock_rapidata.order.create_classification_order.return_value = order

    asyncio.run(tools.ask_multiple_choice("Q", ["A", "B"], n=10))

    _, kwargs = mock_rapidata.order.create_classification_order.call_args
    assert kwargs["responses_per_datapoint"] == RESPONSES_PER_DATAPOINT


def test_ask_multiple_choice_no_language_filter_when_omitted(mock_rapidata):
    order = make_order("mc::Q")
    mock_rapidata.order.create_classification_order.return_value = order

    asyncio.run(tools.ask_multiple_choice("Q", ["A", "B"], n=10))

    _, kwargs = mock_rapidata.order.create_classification_order.call_args
    assert kwargs["filters"] == []


def test_ask_multiple_choice_language_filter_applied(mock_rapidata):
    from rapidata import LanguageFilter

    order = make_order("mc::Q")
    mock_rapidata.order.create_classification_order.return_value = order

    asyncio.run(tools.ask_multiple_choice("Q", ["A", "B"], n=10, language="fr"))

    _, kwargs = mock_rapidata.order.create_classification_order.call_args
    assert len(kwargs["filters"]) == 1
    assert isinstance(kwargs["filters"][0], LanguageFilter)


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def test_compare_returns_order_id(mock_rapidata):
    order = make_order("cmp::Which is better?")
    mock_rapidata.order.create_compare_order.return_value = order

    result = asyncio.run(tools.compare("Which is better?", "Option A", "Option B", n=10))

    assert result == "ord_123"


def test_compare_calls_correct_sdk_method(mock_rapidata):
    order = make_order("cmp::Q")
    mock_rapidata.order.create_compare_order.return_value = order

    asyncio.run(tools.compare("Q", "A", "B", n=10))

    mock_rapidata.order.create_compare_order.assert_called_once()


def test_compare_passes_options_as_pairs(mock_rapidata):
    order = make_order("cmp::Q")
    mock_rapidata.order.create_compare_order.return_value = order

    asyncio.run(tools.compare("Q", "Alpha", "Beta", n=10))

    _, kwargs = mock_rapidata.order.create_compare_order.call_args
    assert kwargs["datapoints"] == [["Alpha", "Beta"]]


def test_compare_hardcodes_responses_per_datapoint(mock_rapidata):
    order = make_order("cmp::Q")
    mock_rapidata.order.create_compare_order.return_value = order

    asyncio.run(tools.compare("Q", "A", "B", n=10))

    _, kwargs = mock_rapidata.order.create_compare_order.call_args
    assert kwargs["responses_per_datapoint"] == RESPONSES_PER_DATAPOINT


def test_compare_no_language_filter_when_omitted(mock_rapidata):
    order = make_order("cmp::Q")
    mock_rapidata.order.create_compare_order.return_value = order

    asyncio.run(tools.compare("Q", "A", "B", n=10))

    _, kwargs = mock_rapidata.order.create_compare_order.call_args
    assert kwargs["filters"] == []


def test_compare_language_filter_applied(mock_rapidata):
    from rapidata import LanguageFilter

    order = make_order("cmp::Q")
    mock_rapidata.order.create_compare_order.return_value = order

    asyncio.run(tools.compare("Q", "A", "B", n=10, language="de"))

    _, kwargs = mock_rapidata.order.create_compare_order.call_args
    assert isinstance(kwargs["filters"][0], LanguageFilter)


def test_compare_n_greater_than_10_creates_multiple_pairs(mock_rapidata):
    order = make_order("cmp::Q")
    mock_rapidata.order.create_compare_order.return_value = order

    asyncio.run(tools.compare("Q", "A", "B", n=30))

    _, kwargs = mock_rapidata.order.create_compare_order.call_args
    assert len(kwargs["datapoints"]) == 3
    assert all(pair == ["A", "B"] for pair in kwargs["datapoints"])


# ---------------------------------------------------------------------------
# rank
# ---------------------------------------------------------------------------


def test_rank_returns_order_id(mock_rapidata):
    order = make_order("rnk::Rank these")
    mock_rapidata.order.create_ranking_order.return_value = order

    result = asyncio.run(tools.rank("Rank these", ["X", "Y", "Z"], n=50))

    assert result == "ord_123"


def test_rank_calls_correct_sdk_method(mock_rapidata):
    order = make_order("rnk::Q")
    mock_rapidata.order.create_ranking_order.return_value = order

    asyncio.run(tools.rank("Q", ["X", "Y"], n=20))

    mock_rapidata.order.create_ranking_order.assert_called_once()


def test_rank_maps_n_to_comparison_budget(mock_rapidata):
    order = make_order("rnk::Q")
    mock_rapidata.order.create_ranking_order.return_value = order

    asyncio.run(tools.rank("Q", ["X", "Y", "Z"], n=50))

    _, kwargs = mock_rapidata.order.create_ranking_order.call_args
    assert kwargs["comparison_budget_per_ranking"] == 50


def test_rank_passes_items_as_datapoints(mock_rapidata):
    order = make_order("rnk::Q")
    mock_rapidata.order.create_ranking_order.return_value = order

    asyncio.run(tools.rank("Q", ["item1", "item2", "item3"], n=30))

    _, kwargs = mock_rapidata.order.create_ranking_order.call_args
    assert kwargs["datapoints"] == [["item1", "item2", "item3"]]


# ---------------------------------------------------------------------------
# check_progress
# ---------------------------------------------------------------------------


def test_check_progress_returns_progress_result(mock_rapidata):
    order = make_order("ft::Q")
    order.get_status.return_value = "Completed"
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.check_progress("ord_123"))

    assert isinstance(result, ProgressResult)


def test_check_progress_completed(mock_rapidata):
    order = make_order("ft::Q")
    order.get_status.return_value = "Completed"
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.check_progress("ord_123"))

    assert result.is_complete is True
    assert result.status == "Completed"
    assert result.order_id == "ord_123"


def test_check_progress_processing(mock_rapidata):
    order = make_order("ft::Q")
    order.get_status.return_value = "Processing"
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.check_progress("ord_123"))

    assert result.is_complete is False
    assert result.status == "Processing"


def test_check_progress_fetches_by_order_id(mock_rapidata):
    order = make_order("ft::Q")
    order.get_status.return_value = "Submitted"
    mock_rapidata.order.get_order_by_id.return_value = order

    asyncio.run(tools.check_progress("ord_xyz"))

    mock_rapidata.order.get_order_by_id.assert_called_once_with("ord_xyz")


# ---------------------------------------------------------------------------
# get_results — free text
# ---------------------------------------------------------------------------


def test_get_results_free_text_returns_correct_type(mock_rapidata):
    order = make_order("ft::Tell me something")
    df = pd.DataFrame({"response": ["hello", "world", "foo"]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert isinstance(result, FreeTextResult)


def test_get_results_free_text_n_responses(mock_rapidata):
    order = make_order("ft::Q")
    df = pd.DataFrame({"response": ["a", "b", "c", "d"]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.n_responses == 4
    assert len(result.responses) == 4


def test_get_results_free_text_order_type(mock_rapidata):
    order = make_order("ft::Q")
    df = pd.DataFrame({"response": ["x"]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.order_type == "free_text"


# ---------------------------------------------------------------------------
# get_results — multiple choice
# ---------------------------------------------------------------------------


def test_get_results_multiple_choice_returns_correct_type(mock_rapidata):
    order = make_order("mc::Which color?")
    df = pd.DataFrame({"aggregatedResults_red": [3], "aggregatedResults_blue": [2]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert isinstance(result, MultipleChoiceResult)


def test_get_results_multiple_choice_winner(mock_rapidata):
    order = make_order("mc::Q")
    df = pd.DataFrame({"aggregatedResults_red": [3], "aggregatedResults_blue": [2]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.winner == "red"
    assert result.n_responses == 5


def test_get_results_multiple_choice_distribution(mock_rapidata):
    order = make_order("mc::Q")
    df = pd.DataFrame({"aggregatedResults_A": [3], "aggregatedResults_B": [1], "aggregatedResults_C": [1]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.distribution["A"] == 3
    assert result.distribution["B"] == 1
    assert result.distribution["C"] == 1


def test_get_results_multiple_choice_confidence(mock_rapidata):
    order = make_order("mc::Q")
    df = pd.DataFrame({"aggregatedResults_A": [3], "aggregatedResults_B": [2]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.confidence == pytest.approx(0.6)


def test_get_results_multiple_choice_order_type(mock_rapidata):
    order = make_order("mc::Q")
    df = pd.DataFrame({"aggregatedResults_A": [1]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.order_type == "multiple_choice"


# ---------------------------------------------------------------------------
# get_results — compare
# ---------------------------------------------------------------------------


def test_get_results_compare_returns_correct_type(mock_rapidata):
    order = make_order("cmp::Which is better?")
    df = pd.DataFrame({"a_votes": [7], "b_votes": [3]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert isinstance(result, CompareResult)


def test_get_results_compare_winner_option_a(mock_rapidata):
    order = make_order("cmp::Q")
    df = pd.DataFrame({"a_votes": [8], "b_votes": [2]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.winner == "option_a"
    assert result.option_a_votes == 8
    assert result.option_b_votes == 2
    assert result.n_responses == 10


def test_get_results_compare_winner_option_b(mock_rapidata):
    order = make_order("cmp::Q")
    df = pd.DataFrame({"a_votes": [3], "b_votes": [7]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.winner == "option_b"


def test_get_results_compare_confidence(mock_rapidata):
    order = make_order("cmp::Q")
    df = pd.DataFrame({"a_votes": [6], "b_votes": [4]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.confidence == pytest.approx(0.6)
    assert result.order_type == "compare"


# ---------------------------------------------------------------------------
# get_results — rank
# ---------------------------------------------------------------------------


def test_get_results_rank_returns_correct_type(mock_rapidata):
    order = make_order("rnk::Rank these")
    df = pd.DataFrame({"item": ["X", "Y", "Z"], "score": [0.9, 0.5, 0.3]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert isinstance(result, RankResult)


def test_get_results_rank_ordered_correctly(mock_rapidata):
    order = make_order("rnk::Q")
    df = pd.DataFrame({"item": ["A", "B", "C"], "score": [0.3, 0.9, 0.5]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.rankings[0].item == "B"
    assert result.rankings[0].rank == 1
    assert result.rankings[1].item == "C"
    assert result.rankings[2].item == "A"


def test_get_results_rank_n_responses(mock_rapidata):
    order = make_order("rnk::Q")
    df = pd.DataFrame({"item": ["X", "Y"], "score": [0.8, 0.2]})
    raw = MagicMock()
    raw.to_pandas.return_value = df
    order.get_results.return_value = raw
    mock_rapidata.order.get_order_by_id.return_value = order

    result = asyncio.run(tools.get_results("ord_123"))

    assert result.n_responses == 2
    assert result.order_type == "rank"
