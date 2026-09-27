"""Adapter for `dataframely <https://github.com/quantco/dataframely>`_ schemas.

A dataframely schema exposes ``is_valid(df) -> bool``: ``True`` when the frame
is valid.  ``shrink_rows`` needs the *failure* predicate (``True`` while the
frame is invalid), so this module inverts it.

Requires the ``dataframely`` extra::

    uv sync --extra dataframely
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import dataframely  # noqa: F401 - imported only to fail fast when missing
except ImportError as exc:  # pragma: no cover - depends on install
    msg = (
        "pycheck.ext.dataframely requires dataframely; install it with "
        "`uv sync --extra dataframely` (or `pip install 'pycheck[dataframely]'`)"
    )
    raise ImportError(msg) from exc

from pycheck.ext._adapter import (
    DEFAULT_MAX_EVALS,
    FailPredicate,
    Repro,
    make_shrink_rows,
)

if TYPE_CHECKING:
    import dataframely as dy
    import polars as pl


def as_predicate(schema: type[dy.Schema]) -> FailPredicate:
    """Return a ``DataFrame -> bool`` failure predicate for ``schema``.

    ``True`` while the frame fails ``schema.is_valid``.  ``is_valid`` returning
    ``None`` is a bug in the schema and panics rather than reading as a miss.
    """

    def fails(df: pl.DataFrame) -> bool:
        result = schema.is_valid(df)
        assert result is not None, "is_valid returned None; the contract requires a bool"
        return not bool(result)

    return fails


shrink_rows = make_shrink_rows(as_predicate)


__all__ = ["DEFAULT_MAX_EVALS", "FailPredicate", "Repro", "as_predicate", "shrink_rows"]
