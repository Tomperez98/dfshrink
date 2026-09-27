"""Tests for the per-library adapters in :mod:`dfshrink.ext`.

Each adapter module imports its real library at import time, so these tests go
through :func:`pytest.importorskip` and are skipped unless the matching extra
is installed:

    uv sync --extra validators

Note: the pandera tests build a ``pa.DataFrameSchema`` rather than a
``DataFrameModel`` subclass.  ``DataFrameModel`` stores ``pa.typing.Series[int]``
as a string annotation and resolves it against module globals, where the
function-local ``pa`` from ``importorskip`` does not exist.
"""

from __future__ import annotations

from typing import Annotated

import polars as pl
import pytest


def test_dataframely_predicate_is_inverted() -> None:
    dy = pytest.importorskip("dataframely")
    from dfshrink.ext.dataframely import as_predicate

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    predicate = as_predicate(HouseSchema)

    assert predicate(pl.DataFrame({"amount": [1, 2, 3]})) is False  # valid -> not failing
    assert predicate(pl.DataFrame({"amount": [1, -2, 3]})) is True  # a bad row -> failing


def test_dataframely_shrink_rows() -> None:
    dy = pytest.importorskip("dataframely")
    from dfshrink.ext.dataframely import shrink_rows as shrink_dataframely

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    repro = shrink_dataframely(pl.DataFrame({"amount": [5, 50, -9, 7, 8]}), HouseSchema)

    assert repro is not None
    assert repro.frame["amount"].to_list() == [-9]
    assert repro.minimality_proven


def test_pandera_predicate_raises_means_failing() -> None:
    pa = pytest.importorskip("pandera.polars")
    from dfshrink.ext.pandera import as_predicate

    schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
    predicate = as_predicate(schema)

    assert predicate(pl.DataFrame({"amount": [1, 2, 3]})) is False  # valid -> not failing
    assert predicate(pl.DataFrame({"amount": [1, -2, 3]})) is True  # validate raises -> failing


def test_pandera_shrink_rows() -> None:
    pa = pytest.importorskip("pandera.polars")
    from dfshrink.ext.pandera import shrink_rows as shrink_pandera

    schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
    repro = shrink_pandera(pl.DataFrame({"amount": [100, 200, -50, 300]}), schema)

    assert repro is not None
    assert repro.frame["amount"].to_list() == [-50]
    assert repro.minimality_proven


def test_pandera_non_schema_error_propagates() -> None:
    """A validator bug (not a schema error) panics instead of reading as "fails"."""
    pytest.importorskip("pandera")
    from dfshrink.ext.pandera import as_predicate

    class Broken:
        def validate(self, df: pl.DataFrame) -> object:
            msg = "validator bug, not invalid data"
            raise TypeError(msg)

    predicate = as_predicate(Broken())

    with pytest.raises(TypeError, match="validator bug"):
        predicate(pl.DataFrame({"amount": [1]}))


def test_patito_predicate_is_inverted() -> None:
    pt = pytest.importorskip("patito")
    from dfshrink.ext.patito import as_predicate

    class House(pt.Model):
        # Annotated rather than ``= pt.Field(...)``: ty strict rejects assigning
        # patito's ``Field -> Any`` to the declared field type.
        amount: Annotated[int, pt.Field(ge=0)]

    predicate = as_predicate(House)

    assert predicate(pl.DataFrame({"amount": [1, 2, 3]})) is False  # valid -> not failing
    assert predicate(pl.DataFrame({"amount": [1, -2, 3]})) is True  # a bad row -> failing


def test_patito_shrink_rows() -> None:
    pt = pytest.importorskip("patito")
    from dfshrink.ext.patito import shrink_rows as shrink_patito

    class House(pt.Model):
        amount: Annotated[int, pt.Field(ge=0)]

    repro = shrink_patito(pl.DataFrame({"amount": [5, 50, -9, 7, 8]}), House)

    assert repro is not None
    assert repro.frame["amount"].to_list() == [-9]
    assert repro.minimality_proven


def test_patito_non_schema_error_propagates() -> None:
    """A model bug (not invalid data) panics instead of reading as "fails"."""
    pytest.importorskip("patito")
    from dfshrink.ext.patito import as_predicate

    class Broken:
        @classmethod
        def validate(cls, dataframe: pl.DataFrame) -> object:  # noqa: ARG003
            msg = "model bug, not invalid data"
            raise TypeError(msg)

    predicate = as_predicate(Broken)

    with pytest.raises(TypeError, match="model bug"):
        predicate(pl.DataFrame({"amount": [1]}))
