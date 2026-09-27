"""Tests for :mod:`pycheck.shrink`.

Each test follows the contract a production caller follows (TEST.md): narrow
on the shape first, one test per failure variant, and keep predicate *bugs*
(panics) separate from expected failures.
"""

from __future__ import annotations

import itertools
from typing import Any, cast

import polars as pl
import pytest
from hypothesis import assume, given, settings, strategies as st

from pycheck.shrink import shrink_rows


def frame(*values: int) -> pl.DataFrame:
    """A one-column frame of ``x`` values.  Crashes the test on misuse."""
    return pl.DataFrame({"x": list(values)})


def sum_positive(df: pl.DataFrame) -> bool:
    """Failure predicate: the column sums to more than zero."""
    return bool(df["x"].sum() > 0)


def at_least_two_positive(df: pl.DataFrame) -> bool:
    """Failure predicate: two or more positive values are present."""
    return int((df["x"] > 0).sum()) >= 2


def at_least_three_positive(df: pl.DataFrame) -> bool:
    """Failure predicate: three or more positive values are present."""
    return int((df["x"] > 0).sum()) >= 3


# --- Expected failure: the input does not fail ------------------------------


def test_returns_none_when_input_does_not_fail() -> None:
    assert shrink_rows(frame(-1, -2, -3), sum_positive) is None


# --- The reduction itself ---------------------------------------------------


def test_reduces_to_a_single_positive_row() -> None:
    repro = shrink_rows(frame(-5, 3, -1, 7, 2), sum_positive)

    assert repro is not None
    assert repro.frame.height == 1
    assert repro.frame["x"].item() > 0
    assert repro.minimality_proven


def test_cannot_reduce_below_the_predicate_minimum() -> None:
    repro = shrink_rows(frame(-5, 3, -1, 7, 2, 9), at_least_two_positive)

    assert repro is not None
    assert repro.frame.height == 2
    assert all(value > 0 for value in repro.frame["x"].to_list())


def test_finds_the_single_pinned_row_among_many() -> None:
    values = [0] * 50
    values[37] = 1

    repro = shrink_rows(
        pl.DataFrame({"x": values}),
        lambda df: bool((df["x"] == 1).any()),
    )

    assert repro is not None
    assert repro.frame.height == 1
    assert repro.frame["x"].to_list() == [1]


def test_result_is_1_minimal() -> None:
    repro = shrink_rows(frame(-5, 3, -1, 7, 2, 9, -2), sum_positive)

    assert repro is not None
    for i in range(repro.frame.height):
        without = repro.frame[[j for j in range(repro.frame.height) if j != i]]
        assert not sum_positive(without), f"row {i} was removable"


def test_preserves_relative_row_order() -> None:
    df = pl.DataFrame({"id": [0, 1, 2, 3, 4], "x": [5, -1, 4, -1, -1]})

    repro = shrink_rows(df, at_least_two_positive)

    assert repro is not None
    assert repro.frame["id"].to_list() == [0, 2]


def test_uses_complement_reduction_when_no_chunk_fails() -> None:
    # Positives are separated by negatives, so no contiguous chunk holds three
    # positive values at once; ddmin must fall back to complement removal to
    # drop the interspersed negatives and reach the three positives.
    values = [1, -1, 1, -1, 1]

    repro = shrink_rows(frame(*values), at_least_three_positive)

    assert repro is not None
    assert repro.minimality_proven
    assert repro.frame.height == 3
    assert repro.frame["x"].to_list() == [1, 1, 1]


def test_preserves_columns_and_dtypes() -> None:
    df = pl.DataFrame({"id": [0, 1, 2, 3], "x": [1, 2, -3, 4], "tag": ["a", "b", "c", "d"]})

    repro = shrink_rows(df, lambda d: bool((d["x"] < 0).any()))

    assert repro is not None
    assert dict(repro.frame.schema) == dict(df.schema)
    assert repro.frame.equals(df[[2]])


def test_reports_how_much_was_removed() -> None:
    repro = shrink_rows(frame(-5, 3, -1, 7, 2, 9, -2), sum_positive)

    assert repro is not None
    assert repro.original_rows == 7
    assert repro.frame.height < repro.original_rows


def test_removed_rows_counts_dropped_rows() -> None:
    repro = shrink_rows(frame(-5, 3, -1, 7, 2), sum_positive)

    assert repro is not None
    assert repro.removed_rows == 4
    assert repro.removed_rows == repro.original_rows - repro.frame.height


# --- Bounds and budget (expected failure: budget runs out) ------------------


def test_budget_exhaustion_returns_partial_but_failing_result() -> None:
    original = frame(-5, 3, -1, 7, 2)

    repro = shrink_rows(original, sum_positive, max_evals=1)

    assert repro is not None
    assert not repro.minimality_proven
    assert repro.predicate_calls == 1
    assert repro.frame.equals(original)
    assert sum_positive(repro.frame)


def test_single_row_frame_is_complete_without_calls_beyond_one() -> None:
    repro = shrink_rows(frame(9), sum_positive)

    assert repro is not None
    assert repro.minimality_proven
    assert repro.frame.height == 1
    assert repro.predicate_calls == 1


def test_budget_boundary_exactly_sufficient_proves_minimality() -> None:
    # Reducing (-5, 3, -1, 7, 2) under sum_positive takes exactly 4 predicate
    # calls: 4 is just enough to prove 1-minimality, 3 falls one short.
    original = frame(-5, 3, -1, 7, 2)

    proven = shrink_rows(original, sum_positive, max_evals=4)
    short = shrink_rows(original, sum_positive, max_evals=3)

    assert proven is not None
    assert proven.minimality_proven
    assert proven.predicate_calls == 4

    assert short is not None
    assert not short.minimality_proven
    assert short.predicate_calls == 3
    assert short.frame.height > proven.frame.height
    assert sum_positive(short.frame)


def test_is_deterministic() -> None:
    first = shrink_rows(frame(-5, 3, -1, 7, 2, 9, -2), sum_positive)
    second = shrink_rows(frame(-5, 3, -1, 7, 2, 9, -2), sum_positive)

    assert first is not None
    assert second is not None
    assert first.frame.equals(second.frame)
    assert first.predicate_calls == second.predicate_calls


# --- Defects (bugs panic) ---------------------------------------------------


def test_empty_frame_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one row"):
        shrink_rows(pl.DataFrame({"x": []}), sum_positive)


def test_non_positive_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_evals"):
        shrink_rows(frame(1, 2, 3), sum_positive, max_evals=0)


def test_predicate_exception_propagates_unchanged() -> None:
    def exploding(_df: pl.DataFrame) -> bool:
        msg = "predicate bug"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="predicate bug"):
        shrink_rows(frame(1, 2, 3), exploding)


def test_predicate_returning_none_is_rejected() -> None:
    def returns_none(_df: pl.DataFrame) -> bool:
        result: Any = None
        return cast("bool", result)

    with pytest.raises(TypeError, match="None"):
        shrink_rows(frame(1, 2, 3), returns_none)


# --- Properties (TEST.md: test the contract as properties) -----------------


@given(st.lists(st.integers(min_value=-9, max_value=9), min_size=1, max_size=40))
@settings(max_examples=200, deadline=None)
def test_property_reproduces_is_minimal_and_ordered(values: list[int]) -> None:
    df = pl.DataFrame({"id": list(range(len(values))), "x": values})
    assume(sum_positive(df))

    repro = shrink_rows(df, sum_positive)

    assert repro is not None
    assert sum_positive(repro.frame)
    assert 1 <= repro.frame.height <= len(values)

    ids = repro.frame["id"].to_list()
    assert ids == sorted(ids), "row order must be preserved"

    # Regression guard: ddmin stays near O(n log n), never O(n²).  For the
    # "sum > 0" failure the minimal repro is a single positive row, reached in
    # ~2·log2(n) calls; the headroom trips only on an O(n²) regression.
    assert repro.predicate_calls <= 2 * len(values).bit_length() + 10

    if repro.minimality_proven:
        for i in range(repro.frame.height):
            without = repro.frame[[j for j in range(repro.frame.height) if j != i]]
            assert not sum_positive(without), f"row {i} was removable"


@given(
    st.lists(st.integers(min_value=-9, max_value=9), min_size=1, max_size=40),
    st.integers(min_value=1, max_value=60),
)
@settings(max_examples=200, deadline=None)
def test_property_never_exceeds_the_budget(values: list[int], max_evals: int) -> None:
    repro = shrink_rows(pl.DataFrame({"x": values}), sum_positive, max_evals=max_evals)

    if repro is not None:
        assert repro.predicate_calls <= max_evals


@given(
    st.lists(st.integers(min_value=-9, max_value=9), min_size=1, max_size=40),
    st.integers(min_value=1, max_value=40),
)
@settings(max_examples=200, deadline=None)
def test_property_result_always_fails_and_is_a_subsequence(
    values: list[int], max_evals: int
) -> None:
    df = pl.DataFrame({"id": list(range(len(values))), "x": values})

    repro = shrink_rows(df, sum_positive, max_evals=max_evals)

    if repro is None:
        assert not sum_positive(df)
        return

    assert sum_positive(repro.frame)
    ids = repro.frame["id"].to_list()
    assert ids == sorted(ids)
    assert repro.frame.equals(df[ids])


@given(st.lists(st.integers(min_value=-9, max_value=9), min_size=1, max_size=7))
@settings(max_examples=150, deadline=None)
def test_property_height_matches_exhaustive_minimum(values: list[int]) -> None:
    df = pl.DataFrame({"x": values})

    repro = shrink_rows(df, sum_positive)

    if repro is None:
        assert not sum_positive(df)
        return

    assert repro.minimality_proven
    # sum_positive is monotone, so the 1-minimal result is also the global
    # minimum; verify it against brute force over every non-empty subset.
    true_min = min(
        size
        for size in range(1, len(values) + 1)
        for subset in itertools.combinations(range(len(values)), size)
        if sum_positive(df[list(subset)])
    )
    assert repro.frame.height == true_min
