"""Tests for :func:`dfshrink.minimize_columns` (Phase 3: column reduction).

Shrinking drops rows, value minimization moves cells; column reduction removes
whole columns the failing rule does not read.  These tests pin the acceptance
criterion (an irrelevant extra column disappears, the frame still fails on the
rest), the "same reason" contract (a drop is rejected when it changes *why* the
frame fails), the two-dimensional minimality reporting, and the panics for
caller bugs.
"""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import assume, given, settings, strategies as st

from dfshrink import ColumnReduction, Failure, Repro, minimize_columns


def repro(frame: pl.DataFrame, *, proven: bool = True) -> Repro:
    """Wrap ``frame`` as a :class:`Repro`; ``proven`` sets the row-minimality flag."""
    return Repro(
        frame=frame,
        original_rows=frame.height,
        predicate_calls=0,
        minimality_proven=proven,
    )


def explain_negative(df: pl.DataFrame) -> Failure | None:
    """A dependency-free explainer: fails rule ``amount|min`` when present."""
    if "amount" not in df.columns:
        return Failure(rule="structural", column=None, message="missing amount", invalid_rows=None)
    bad = df.filter(pl.col("amount") < 0)
    if bad.height == 0:
        return None
    return Failure(rule="amount|min", column="amount", message=None, invalid_rows=bad)


def explain_gate(df: pl.DataFrame) -> Failure | None:
    """Explains ``amount`` first, ``gate`` second; both are needed to name them."""
    if "amount" not in df.columns or "gate" not in df.columns:
        return Failure(rule="structural", column=None, message="missing", invalid_rows=None)
    if bool((df["amount"] < 0).any()):
        return Failure(rule="amount|min", column="amount", message=None, invalid_rows=None)
    if bool((df["gate"] < 0).any()):
        return Failure(rule="gate|min", column="gate", message=None, invalid_rows=None)
    return None


# --- The acceptance criterion ------------------------------------------------


def test_drops_irrelevant_extra_columns() -> None:
    frame = pl.DataFrame(
        {
            "id": [1, 2],
            "amount": [-9, 5],
            "junk": ["a", "b"],
            "debug": [0.5, 1.5],
        },
        schema={"id": pl.Int32, "amount": pl.Int64, "junk": pl.String, "debug": pl.Float64},
    )

    result = minimize_columns(repro(frame), explain_negative)

    assert result.proven
    assert result.dropped_columns == ("id", "junk", "debug")
    assert result.repro.frame.columns == ["amount"]
    assert explain_negative(result.repro.frame) is not None
    # Kept columns keep their rows, dtypes, and order.
    assert result.repro.frame["amount"].to_list() == [-9, 5]
    assert result.repro.frame["amount"].dtype == pl.Int64


def test_never_drops_the_failing_column() -> None:
    frame = pl.DataFrame({"amount": [-9], "junk": [1]})

    result = minimize_columns(repro(frame), explain_negative)

    assert result.repro.frame.columns == ["amount"]
    assert result.dropped_columns == ("junk",)


def test_rejects_a_drop_that_changes_the_reason() -> None:
    """``gate`` is not referenced by the failing rule but removing it changes why."""
    frame = pl.DataFrame({"amount": [-9], "gate": [-5], "junk": [1]})

    result = minimize_columns(repro(frame), explain_gate)

    assert result.proven
    assert result.dropped_columns == ("junk",)
    assert result.repro.frame.columns == ["amount", "gate"]
    assert result.failure is not None
    assert result.failure.rule == "amount|min"
    assert result.failure.column == "amount"


def test_single_column_frame_is_trivially_minimal() -> None:
    frame = pl.DataFrame({"amount": [-9]})

    result = minimize_columns(repro(frame), explain_negative)

    assert result.proven
    assert result.dropped_columns == ()


def test_complement_step_drops_an_unneeded_column() -> None:
    """No single chunk keeps the reason, but removing one does (ddmin complement)."""

    def explain(df: pl.DataFrame) -> Failure | None:
        if not {"amount", "gate", "extra"} <= set(df.columns):
            return Failure(rule="triad|min", column=None, message="missing", invalid_rows=None)
        return Failure(rule="triad|min", column="amount", message=None, invalid_rows=None)

    frame = pl.DataFrame({"amount": [1], "gate": [2], "extra": [3], "junk": [4]})

    result = minimize_columns(repro(frame), explain)

    assert result.proven
    assert result.dropped_columns == ("junk",)
    assert result.repro.frame.columns == ["amount", "gate", "extra"]


def test_rows_remain_minimal_when_every_row_is_needed() -> None:
    """A two-offender rule keeps both rows, so the row flag stays proven."""

    def explain(df: pl.DataFrame) -> Failure | None:
        if "amount" not in df.columns:
            return Failure(rule="two|min", column=None, message="missing", invalid_rows=None)
        if int((df["amount"] < 0).sum()) >= 2:
            return Failure(rule="two|min", column="amount", message=None, invalid_rows=None)
        return None

    frame = pl.DataFrame({"amount": [-9, -8], "junk": [1, 2]})

    result = minimize_columns(repro(frame), explain)

    assert result.proven
    assert result.dropped_columns == ("junk",)
    assert result.repro.minimality_proven


def test_exhausted_budget_during_the_search() -> None:
    def explain(df: pl.DataFrame) -> Failure | None:
        if not {"amount", "gate", "extra"} <= set(df.columns):
            return Failure(rule="triad|min", column=None, message="missing", invalid_rows=None)
        return Failure(rule="triad|min", column="amount", message=None, invalid_rows=None)

    frame = pl.DataFrame({"amount": [1], "gate": [2], "extra": [3]})

    result = minimize_columns(repro(frame), explain, max_evals=2)

    assert not result.proven
    assert result.failure is not None
    assert result.repro.frame.columns == ["amount", "gate", "extra"]


# --- Two-dimensional minimality reporting ------------------------------------


def test_rechecks_rows_against_the_preserved_reason() -> None:
    """Dropping ``gate`` makes the reason narrower, so a kept row becomes removable.

    The flag must reflect that the rows are no longer minimal.
    """

    def explain(df: pl.DataFrame) -> Failure | None:
        if "amount" not in df.columns:
            return Failure(rule="structural", column=None, message="missing", invalid_rows=None)
        if "gate" not in df.columns:
            if bool((df["amount"] < 0).any()):
                return Failure(rule="amount|min", column="amount", message=None, invalid_rows=None)
            return None
        if bool((df["amount"] < 0).any()) and bool((df["gate"] < 0).any()):
            return Failure(rule="amount|min", column="amount", message=None, invalid_rows=None)
        return None

    # One row supplies the amount offender, the other the gate offender.
    frame = pl.DataFrame({"amount": [-1, 1], "gate": [1, -1]})

    result = minimize_columns(repro(frame), explain)

    assert result.proven  # column-minimal: only `amount` can stay
    assert result.dropped_columns == ("gate",)
    assert result.repro.frame.columns == ["amount"]
    assert not result.repro.minimality_proven  # but the rows are no longer minimal


def test_propagates_an_unproven_row_shrink() -> None:
    frame = pl.DataFrame({"amount": [-9], "junk": [1]})

    result = minimize_columns(repro(frame, proven=False), explain_negative)

    assert not result.repro.minimality_proven
    assert result.proven  # the column dimension can still be proven


# --- Budget: expected failures return values ---------------------------------


def test_tiny_budget_names_the_reason_but_proves_nothing() -> None:
    frame = pl.DataFrame({"amount": [-9], "junk": [1]})

    result = minimize_columns(repro(frame), explain_negative, max_evals=1)

    assert not result.proven
    assert result.failure is not None
    assert result.dropped_columns == ()
    assert result.repro.frame.columns == ["amount", "junk"]


def test_exhausted_budget_returns_the_frame_unproven() -> None:
    frame = pl.DataFrame({"amount": [-9], "a": [1], "b": [2], "c": [3]})

    result = minimize_columns(repro(frame), explain_negative, max_evals=2)

    assert not result.proven
    assert result.failure is not None
    assert explain_negative(result.repro.frame) is not None


def test_counts_its_own_predicate_calls() -> None:
    frame = pl.DataFrame({"amount": [-9], "junk": [1]})

    result = minimize_columns(repro(frame), explain_negative)

    assert result.predicate_calls > 0
    # Row shrinking's calls belong to the source Repro, not this reduction.
    assert result.repro.predicate_calls == 0


# --- Defects (bugs panic) ----------------------------------------------------


def test_rejects_non_positive_budget() -> None:
    frame = pl.DataFrame({"amount": [-9]})

    with pytest.raises(ValueError, match="max_evals"):
        minimize_columns(repro(frame), explain_negative, max_evals=0)


def test_rejects_a_source_that_does_not_fail() -> None:
    frame = pl.DataFrame({"amount": [1, 2]})

    with pytest.raises(ValueError, match="failing frame"):
        minimize_columns(repro(frame), explain_negative)


def test_rejects_a_reason_with_no_rule() -> None:
    def structural(_df: pl.DataFrame) -> Failure | None:
        return Failure(rule=None, column=None, message="missing", invalid_rows=None)

    with pytest.raises(ValueError, match="named failing rule"):
        minimize_columns(repro(pl.DataFrame({"amount": [-9]})), structural)


# --- Package surface ---------------------------------------------------------


def test_result_and_repr_are_exported() -> None:
    result = minimize_columns(repro(pl.DataFrame({"amount": [-9], "junk": [1]})), explain_negative)

    assert isinstance(result, ColumnReduction)
    assert repr(result).startswith("ColumnReduction(dropped=1")
    assert "columns_left=1" in repr(result)


# --- Properties (TEST.md: test the contract as properties) --------------------


@given(
    values=st.lists(st.integers(min_value=-9, max_value=9), min_size=1, max_size=12),
    n_extra=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=150, deadline=None)
def test_property_keeps_the_failing_column_and_drops_the_rest(
    values: list[int], n_extra: int
) -> None:
    assume(any(value < 0 for value in values))
    extras = [f"c{i}" for i in range(n_extra)]
    data: dict[str, list[int]] = {"amount": values}
    for name in extras:
        data[name] = [0] * len(values)
    df = pl.DataFrame(data)

    result = minimize_columns(repro(df), explain_negative)

    assert result.proven
    assert result.repro.frame.columns == ["amount"]
    assert set(result.dropped_columns) == set(extras)
    assert result.repro.frame["amount"].to_list() == values
    assert result.failure.rule == "amount|min"
    assert explain_negative(result.repro.frame) is not None


# --- Validator integrations --------------------------------------------------


def test_dataframely_drops_an_undeclared_column() -> None:
    dy = pytest.importorskip("dataframely")
    import dfshrink.ext.dataframely as adapter

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)
        note = dy.String(nullable=True)

    df = pl.DataFrame({"amount": [5, -9, 7], "note": ["a", "b", "c"], "debug": [1, 2, 3]})
    shrunk = adapter.shrink_rows(df, HouseSchema)
    assert shrunk is not None

    result = minimize_columns(shrunk, adapter.as_failure(HouseSchema))

    assert result.proven
    assert result.dropped_columns == ("debug",)
    assert result.repro.frame.columns == ["amount", "note"]
    assert HouseSchema.is_valid(result.repro.frame) is False
    assert result.failure is not None
    assert result.failure.rule == "amount|min"


def test_dataframely_diagnose_columns_flag_keeps_the_reason() -> None:
    dy = pytest.importorskip("dataframely")
    import dfshrink.ext.dataframely as adapter

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)
        note = dy.String(nullable=True)

    df = pl.DataFrame({"amount": [5, -9, 7], "note": ["a", "b", "c"], "debug": [1, 2, 3]})

    found = adapter.diagnose(df, HouseSchema, columns=True)

    assert found is not None
    assert found.repro.frame.columns == ["amount", "note"]
    assert found.failure is not None
    assert found.failure.rule == "amount|min"


def test_pandera_drops_irrelevant_columns() -> None:
    pa = pytest.importorskip("pandera.polars")
    import dfshrink.ext.pandera as adapter

    schema = pa.DataFrameSchema(
        {"amount": pa.Column(int, pa.Check.gt(0)), "note": pa.Column(str, nullable=True)}
    )
    df = pl.DataFrame({"amount": [5, -9, 7], "note": ["a", "b", "c"], "debug": [1, 2, 3]})
    found = adapter.diagnose(df, schema)
    assert found is not None
    assert found.repro.frame.columns == ["amount", "note", "debug"]

    result = minimize_columns(found, adapter.as_failure(schema))

    assert result.proven
    assert result.dropped_columns == ("note", "debug")
    assert result.repro.frame.columns == ["amount"]
    assert result.failure is not None
    assert result.failure.rule == "greater_than(0)"


def test_pandera_diagnose_columns_flag_reduces_the_repro() -> None:
    pa = pytest.importorskip("pandera.polars")
    import dfshrink.ext.pandera as adapter

    schema = pa.DataFrameSchema(
        {"amount": pa.Column(int, pa.Check.gt(0)), "note": pa.Column(str, nullable=True)}
    )
    df = pl.DataFrame({"amount": [5, -9, 7], "note": ["a", "b", "c"], "debug": [1, 2, 3]})

    found = adapter.diagnose(df, schema, columns=True)

    assert found is not None
    assert found.repro.frame.columns == ["amount"]
