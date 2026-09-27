"""Pytest helper: fail a test with a minimal repro and the failing rule.

``assert_valid`` is the pytest-shaped replacement for
``assert schema.is_valid(df)``: it runs the adapter's ``diagnose`` and, when the
frame fails, raises ``AssertionError`` naming the rule/column and showing the
minimal repro -- instead of the validator's raw traceback.

Pass the adapter's ``diagnose`` as the seam, so this module imports no validator
library::

    from pycheck.ext.dataframely import diagnose
    from pycheck.ext.pytest import assert_valid

    def test_house_schema(df):
        assert_valid(df, HouseSchema, diagnose=diagnose)

It works unchanged inside a fixture: ``assert_valid`` neither imports pytest nor
touches global state; it just raises ``AssertionError``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pycheck.ext._adapter import DEFAULT_MAX_EVALS, Diagnose, Diagnosis

if TYPE_CHECKING:
    import polars as pl

__all__ = ["assert_valid"]


def assert_valid[SchemaT](
    frame: pl.DataFrame,
    schema: SchemaT,
    *,
    diagnose: Diagnose[SchemaT],
    max_evals: int = DEFAULT_MAX_EVALS,
) -> None:
    """Return ``None`` when ``frame`` passes ``schema``; else fail the test.

    On failure, raises ``AssertionError`` whose message names the failing
    rule/column (Phase 0) and shows the minimal repro table
    (:meth:`pycheck.Diagnosis.to_markdown`).
    """
    found: Diagnosis | None = diagnose(frame, schema, max_evals=max_evals)
    if found is None:
        return
    raise AssertionError(found.to_markdown())
