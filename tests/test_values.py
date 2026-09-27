"""Tests for :func:`dfshrink.minimize_values` (Phase 2: value/boundary minimization).

Shrinking drops rows; this step moves the flagged column's values to the failing
boundary.  The contract tests below pin the boundary, the direction inference,
the honest ``proven`` flag, and the panics for caller bugs (unknown column,
unknown direction, non-numeric cells).
"""

from __future__ import annotations

import math
import sys
from typing import Any, cast

import polars as pl
import pytest
from hypothesis import given, settings, strategies as st

from dfshrink import Repro, ValueReduction, direction_for_rule, minimize_values, shrink_rows

NEGATIVE = lambda d: bool((d["amount"] < 0).any())  # noqa: E731
POSITIVE = lambda d: bool((d["amount"] > 0).any())  # noqa: E731


def repro(frame: pl.DataFrame) -> Repro:
    """Wrap ``frame`` as a :class:`Repro`.  Crashes the test on misuse."""
    return Repro(
        frame=frame,
        original_rows=frame.height,
        predicate_calls=0,
        minimality_proven=True,
    )


def two_negatives(frame: pl.DataFrame) -> bool:
    return int((frame["amount"] < 0).sum()) >= 2


# --- The acceptance criterion ------------------------------------------------


def test_min_rule_shrinks_to_the_last_failing_value() -> None:
    frame = pl.DataFrame({"amount": [-9]})

    result = minimize_values(repro(frame), NEGATIVE, column="amount", direction="increase")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-1]
    assert NEGATIVE(result.repro.frame)


def test_max_rule_shrinks_up_to_the_last_failing_value() -> None:
    frame = pl.DataFrame({"amount": [9]})

    result = minimize_values(repro(frame), POSITIVE, column="amount", direction="decrease")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [1]
    assert POSITIVE(result.repro.frame)


# --- Direction inference -----------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ("amount|min", "increase"),
        ("amount|min_exclusive", "increase"),
        ("greater_than(0)", "increase"),
        ("ge", "increase"),
        ("amount|gt", "increase"),
        (">=", "increase"),
        ("positive", "increase"),
        ("amount|max", "decrease"),
        ("less_than(0)", "decrease"),
        ("le", "decrease"),
        ("negative", "decrease"),
        ("isin([1, 2])", None),
        ("unique", None),
        ("range", None),
        (None, None),
    ],
)
def test_direction_for_rule_reads_the_rule_name(rule: str | None, expected: str | None) -> None:
    assert direction_for_rule(rule) == expected


def test_diagnosis_supplies_column_and_direction() -> None:
    dy = pytest.importorskip("dataframely")
    from dfshrink.ext.dataframely import as_predicate, diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    found = diagnose(pl.DataFrame({"amount": [5, -9, 7]}), HouseSchema)

    assert found is not None
    result = minimize_values(found, as_predicate(HouseSchema))

    assert result.column == "amount"
    assert result.direction == "increase"
    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-1]


# --- Shape and provenance ----------------------------------------------------


def test_preserves_rows_dtypes_and_other_columns() -> None:
    frame = pl.DataFrame(
        {"id": [0, 1], "amount": [-5, -7], "tag": ["a", "b"]},
        schema={"id": pl.Int32, "amount": pl.Int64, "tag": pl.String},
    )

    result = minimize_values(repro(frame), two_negatives, column="amount", direction="increase")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-1, -1]
    assert result.repro.frame["id"].to_list() == [0, 1]
    assert result.repro.frame["tag"].to_list() == ["a", "b"]
    assert dict(result.repro.frame.schema) == dict(frame.schema)
    assert two_negatives(result.repro.frame)


def test_integer_boundary_respects_the_dtype() -> None:
    frame = pl.DataFrame({"amount": [-100]}, schema={"amount": pl.Int32})

    result = minimize_values(repro(frame), NEGATIVE, column="amount", direction="increase")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-1]
    assert result.repro.frame["amount"].dtype == pl.Int32


def test_float_boundary_is_the_adjacent_representable_value() -> None:
    frame = pl.DataFrame({"amount": [-9.0]})

    result = minimize_values(repro(frame), NEGATIVE, column="amount", direction="increase")

    assert result.proven
    boundary = result.repro.frame["amount"][0]
    assert boundary < 0
    # The next Float64 toward 0.0 (-0.0) does not fail any more.
    assert not NEGATIVE(pl.DataFrame({"amount": [math.nextafter(boundary, 0.0)]}))


def test_reports_calls_and_leaves_row_minimality_proven() -> None:
    frame = pl.DataFrame({"amount": [-9]})

    result = minimize_values(repro(frame), NEGATIVE, column="amount", direction="increase")

    assert result.predicate_calls > 0
    assert result.repro.minimality_proven
    assert "sequence" not in repr(result)
    assert repr(result).startswith("ValueReduction(column='amount'")


def test_value_reduction_is_exported_from_the_package() -> None:
    assert isinstance(
        minimize_values(
            repro(pl.DataFrame({"amount": [-9]})), NEGATIVE, column="amount", direction="increase"
        ),
        ValueReduction,
    )


# --- Expected failure: no crossing, or budget exhausted ----------------------


def test_no_crossing_leaves_the_value_and_reports_unproven() -> None:
    frame = pl.DataFrame({"amount": [-9]})

    result = minimize_values(
        repro(frame), lambda _d: True, column="amount", direction="increase", max_evals=50
    )

    assert not result.proven
    assert result.repro.frame["amount"].to_list() == [-9]
    assert result.predicate_calls == 50


def test_row_minimality_safety_net_flags_a_removable_row() -> None:
    from dfshrink.values import _rows_still_minimal, _Tracker

    frame = pl.DataFrame({"amount": [-1, -1]})

    assert not _rows_still_minimal(frame, _Tracker(NEGATIVE, 10))


def test_bisection_takes_a_passing_midpoint() -> None:
    # Failing while amount < -5: the first bisection midpoint (-5) already passes,
    # so the high end moves down to it before closing on -6.
    frame = pl.DataFrame({"amount": [-9]})
    fails = lambda d: bool((d["amount"] < -5).any())  # noqa: E731

    result = minimize_values(repro(frame), fails, column="amount", direction="increase")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-6]


def test_unsigned_boundary_uses_the_dtype_bounds() -> None:
    frame = pl.DataFrame({"amount": [9]}, schema={"amount": pl.UInt8})

    result = minimize_values(repro(frame), POSITIVE, column="amount", direction="decrease")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [1]
    assert result.repro.frame["amount"].dtype == pl.UInt8


def test_independent_violations_report_unproven() -> None:
    # Two independent offenders: moving one to the valid region leaves the other
    # failing, so no crossing exists and the step refuses to claim a boundary.
    frame = pl.DataFrame({"amount": [-5, -7]})

    result = minimize_values(repro(frame), NEGATIVE, column="amount", direction="increase")

    assert not result.proven
    assert NEGATIVE(result.repro.frame)


def test_budget_exhaustion_keeps_a_valid_failing_repro() -> None:
    frame = pl.DataFrame({"amount": [-10_000]})

    result = minimize_values(
        repro(frame), NEGATIVE, column="amount", direction="increase", max_evals=2
    )

    assert not result.proven
    assert NEGATIVE(result.repro.frame)


# --- Defects (bugs panic) ----------------------------------------------------


def test_rejects_non_positive_budget() -> None:
    with pytest.raises(ValueError, match="max_evals"):
        minimize_values(
            repro(pl.DataFrame({"amount": [-1]})), NEGATIVE, column="amount", max_evals=0
        )


def test_rejects_a_missing_column() -> None:
    with pytest.raises(ValueError, match="not in the frame"):
        minimize_values(
            repro(pl.DataFrame({"amount": [-1]})), NEGATIVE, column="nope", direction="increase"
        )


def test_rejects_a_source_with_no_column() -> None:
    with pytest.raises(ValueError, match="needs a column"):
        minimize_values(repro(pl.DataFrame({"amount": [-1]})), NEGATIVE, direction="increase")


def test_rejects_a_non_finite_cell() -> None:
    frame = pl.DataFrame({"amount": [float("inf")]})

    with pytest.raises(ValueError, match="non-finite"):
        minimize_values(repro(frame), lambda _d: True, column="amount", direction="increase")


def test_rejects_a_value_at_the_dtype_bound() -> None:
    frame = pl.DataFrame({"amount": [127]}, schema={"amount": pl.Int8})

    result = minimize_values(
        repro(frame), lambda _d: True, column="amount", direction="increase", max_evals=10
    )

    assert not result.proven
    assert result.repro.frame["amount"].to_list() == [127]


def test_rejects_an_unknown_direction() -> None:
    with pytest.raises(ValueError, match="direction"):
        minimize_values(
            repro(pl.DataFrame({"amount": [-1]})),
            NEGATIVE,
            column="amount",
            direction=cast("Any", "sideways"),
        )


def test_rejects_a_non_numeric_column() -> None:
    frame = pl.DataFrame({"tag": ["a"]}, schema={"tag": pl.String})

    with pytest.raises(TypeError, match="String"):
        minimize_values(repro(frame), lambda _d: True, column="tag", direction="increase")


def test_rejects_a_null_cell() -> None:
    frame = pl.DataFrame({"amount": [None]}, schema={"amount": pl.Int64})

    with pytest.raises(ValueError, match="null"):
        minimize_values(repro(frame), lambda _d: True, column="amount", direction="increase")


def test_predicate_returning_none_is_rejected() -> None:
    def returns_none(_df: pl.DataFrame) -> bool:
        result: Any = None
        return cast("bool", result)

    with pytest.raises(TypeError, match="None"):
        minimize_values(
            repro(pl.DataFrame({"amount": [-1]})),
            returns_none,
            column="amount",
            direction="increase",
        )


# --- Numeric helpers (complex internals, unit-tested directly) ----------------


def test_step_nextafter_and_overflow_guards() -> None:
    from dfshrink.values import _step

    # Adding 1.0 to a huge float does not move it, so a one-ulp step is taken.
    assert _step(1e300, 1.0, "increase", None) > 1e300
    # Overflow past the Float64 range clamps instead of returning inf.
    assert _step(1e308, 1e308, "increase", None) == sys.float_info.max


def test_mid_nextafter_guard_for_an_overflowing_span() -> None:
    from dfshrink.values import _mid

    assert _mid(1e308, -1e308, None) < 1e308


# --- Integration with the shrink phase ---------------------------------------


def test_runs_after_shrink_rows_end_to_end() -> None:
    frame = pl.DataFrame({"id": [0, 1, 2], "amount": [-500, 7, 9]})

    shrunk = shrink_rows(frame, NEGATIVE)

    assert shrunk is not None
    assert shrunk.frame["amount"].to_list() == [-500]

    result = minimize_values(shrunk, NEGATIVE, column="amount", direction="increase")

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-1]


# --- Properties (TEST.md: test the contract as properties) -------------------


@given(st.integers(min_value=-(2**40), max_value=-1))
@settings(max_examples=100, deadline=None)
def test_property_negative_int_converges_to_minus_one(value: int) -> None:
    result = minimize_values(
        repro(pl.DataFrame({"amount": [value]})), NEGATIVE, column="amount", direction="increase"
    )

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [-1]


@given(st.integers(min_value=1, max_value=2**40))
@settings(max_examples=100, deadline=None)
def test_property_positive_int_converges_to_one(value: int) -> None:
    result = minimize_values(
        repro(pl.DataFrame({"amount": [value]})), POSITIVE, column="amount", direction="decrease"
    )

    assert result.proven
    assert result.repro.frame["amount"].to_list() == [1]
