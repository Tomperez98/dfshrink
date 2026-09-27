"""Tests for :func:`pycheck.ext.<lib>.diagnose` (Phase 0: failure-aware adapters).

``diagnose`` returns a :class:`pycheck.Diagnosis` -- the minimal failing repro
*plus* the rule/column/rows the validator reported.  These tests pin that the
explainer surfaces the validator's own failure signal, and that ``diagnose``
keeps ``shrink_rows`` semantics (same minimal repro, bugs panic, expected
failures return values).
"""

from __future__ import annotations

from typing import Annotated

import polars as pl
import pytest

# --- dataframely -------------------------------------------------------------


def test_dataframely_diagnose_explains_rule_and_column() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose, shrink_rows

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    df = pl.DataFrame({"amount": [5, 50, -9, 7, 8]})

    result = diagnose(df, HouseSchema)

    assert result is not None
    assert result.repro.frame["amount"].to_list() == [-9]
    assert result.repro.minimality_proven
    assert result.failure is not None
    assert result.failure.rule == "amount|min"
    assert result.failure.column == "amount"
    assert result.failure.invalid_rows is not None
    assert result.failure.invalid_rows["amount"].to_list() == [-9]
    shrunk = shrink_rows(df, HouseSchema)
    assert shrunk is not None
    # diagnose preserves shrink_rows semantics: same minimal repro.
    assert result.repro.frame.equals(shrunk.frame)


def test_dataframely_diagnose_returns_none_when_valid() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    assert diagnose(pl.DataFrame({"amount": [1, 2, 3]}), HouseSchema) is None


def test_dataframely_diagnose_reports_structural_failure_without_rows() -> None:
    """A missing column is a structural failure: no invalid rows to report."""
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    result = diagnose(pl.DataFrame({"other": [1, 2, 3]}), HouseSchema)

    assert result is not None
    assert result.failure is not None
    assert result.failure.invalid_rows is None
    assert result.failure.rule is None


# --- pandera -----------------------------------------------------------------


def test_pandera_diagnose_explains_rule_and_column() -> None:
    pa = pytest.importorskip("pandera.polars")
    from pycheck.ext.pandera import diagnose, shrink_rows

    schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
    df = pl.DataFrame({"amount": [100, 200, -50, 300]})

    result = diagnose(df, schema)

    assert result is not None
    assert result.repro.frame["amount"].to_list() == [-50]
    assert result.repro.minimality_proven
    assert result.failure is not None
    assert result.failure.rule == "greater_than(0)"
    assert result.failure.column == "amount"
    assert result.failure.invalid_rows is not None
    assert result.failure.invalid_rows["amount"].to_list() == [-50]
    shrunk = shrink_rows(df, schema)
    assert shrunk is not None
    assert result.repro.frame.equals(shrunk.frame)


def test_pandera_diagnose_returns_none_when_valid() -> None:
    pa = pytest.importorskip("pandera.polars")
    from pycheck.ext.pandera import diagnose

    schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
    assert diagnose(pl.DataFrame({"amount": [1, 2, 3]}), schema) is None


def test_pandera_diagnose_reports_structural_failure_without_rows() -> None:
    pa = pytest.importorskip("pandera.polars")
    from pycheck.ext.pandera import diagnose

    schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})

    result = diagnose(pl.DataFrame({"other": [1, 2, 3]}), schema)

    assert result is not None
    assert result.failure is not None
    assert result.failure.invalid_rows is None
    assert result.failure.rule is None


# --- patito ------------------------------------------------------------------


def test_patito_diagnose_reports_column_but_no_rows() -> None:
    """Patito names the column but not the failing rows, so shrinking falls back."""
    pt = pytest.importorskip("patito")
    from pycheck.ext.patito import diagnose, shrink_rows

    class House(pt.Model):
        amount: Annotated[int, pt.Field(ge=0)]

    df = pl.DataFrame({"amount": [5, 50, -9, 7, 8]})

    result = diagnose(df, House)

    assert result is not None
    assert result.repro.frame["amount"].to_list() == [-9]
    assert result.repro.minimality_proven
    assert result.failure is not None
    assert result.failure.column == "amount"
    assert result.failure.rule is not None
    assert result.failure.invalid_rows is None
    shrunk = shrink_rows(df, House)
    assert shrunk is not None
    assert result.repro.frame.equals(shrunk.frame)


def test_patito_diagnose_returns_none_when_valid() -> None:
    pt = pytest.importorskip("patito")
    from pycheck.ext.patito import diagnose

    class House(pt.Model):
        amount: Annotated[int, pt.Field(ge=0)]

    assert diagnose(pl.DataFrame({"amount": [1, 2, 3]}), House) is None


# --- shared contract (exercised through one adapter) -------------------------


def test_diagnose_rejects_empty_frame() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    with pytest.raises(ValueError, match="at least one row"):
        diagnose(pl.DataFrame({"amount": []}), HouseSchema)


def test_diagnose_rejects_non_positive_budget() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    with pytest.raises(ValueError, match="max_evals"):
        diagnose(pl.DataFrame({"amount": [1, -2, 3]}), HouseSchema, max_evals=0)


# --- rendering (Phase 1) -----------------------------------------------------


def test_diagnosis_summary_names_the_rule_and_column() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    found = diagnose(pl.DataFrame({"amount": [5, -9, 7]}), HouseSchema)

    assert found is not None
    assert "column 'amount' fails rule 'amount|min'" in str(found)
    assert repr(found).startswith("Diagnosis(")


def test_diagnosis_markdown_folds_in_the_reason() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    found = diagnose(pl.DataFrame({"amount": [5, -9, 7]}), HouseSchema)

    assert found is not None
    markdown = found.to_markdown()
    assert "Validation failed: column 'amount' fails rule 'amount|min'." in markdown
    assert "| amount (Int64) |" in markdown
    assert "| -9 |" in markdown


def test_failure_repr_does_not_dump_the_frame() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    found = diagnose(pl.DataFrame({"amount": [5, -9, 7]}), HouseSchema)

    assert found is not None
    assert "<1 rows>" in repr(found.failure)
