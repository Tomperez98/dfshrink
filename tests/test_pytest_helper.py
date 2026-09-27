"""Tests for :func:`pycheck.ext.pytest.assert_valid`.

The helper is the pytest-shaped seam: pass any adapter's ``diagnose`` and it
either returns silently or fails the test with the rule/column and the minimal
repro.
"""

from __future__ import annotations

import polars as pl
import pytest


def test_assert_valid_passes_silently_when_valid() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose
    from pycheck.ext.pytest import assert_valid

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    assert assert_valid(pl.DataFrame({"amount": [1, 2, 3]}), HouseSchema, diagnose=diagnose) is None


def test_assert_valid_fails_with_the_rule_and_the_repro() -> None:
    dy = pytest.importorskip("dataframely")
    from pycheck.ext.dataframely import diagnose
    from pycheck.ext.pytest import assert_valid

    class HouseSchema(dy.Schema):
        amount = dy.Int64(nullable=False, min=0)

    with pytest.raises(AssertionError) as info:
        assert_valid(pl.DataFrame({"amount": [5, -9, 7]}), HouseSchema, diagnose=diagnose)

    message = str(info.value)
    assert "column 'amount' fails rule 'amount|min'" in message
    assert "| amount (Int64) |" in message
    assert "| -9 |" in message
