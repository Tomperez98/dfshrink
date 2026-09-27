"""Adapter for `pandera <https://pandera.readthedocs.io/>`_ schemas.

A pandera schema validates by raising: ``validate(df)`` returns normally when
the frame is valid and raises a :class:`pandera.errors.SchemaError` (or
:class:`~pandera.errors.SchemaErrors`) when it is not.  ``shrink_rows`` needs
the *failure* predicate (``True`` while the frame is invalid), so this module
wraps ``validate`` and maps its schema errors to ``True``.

Requires the ``pandera`` extra::

    uv sync --extra pandera
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

try:
    import pandera.errors
except ImportError as exc:  # pragma: no cover - depends on install
    msg = (
        "pycheck.ext.pandera requires pandera; install it with "
        "`uv sync --extra pandera` (or `pip install 'pycheck[pandera]'`)"
    )
    raise ImportError(msg) from exc

from pycheck.ext._adapter import (
    DEFAULT_MAX_EVALS,
    FailPredicate,
    Repro,
    make_shrink_rows,
)

if TYPE_CHECKING:
    import polars as pl

# DataFrameModel.validate raises SchemaError; DataFrameSchema.validate raises
# SchemaErrors.  Both are the "data is invalid" signal, not a schema bug.
_SCHEMA_ERRORS = (pandera.errors.SchemaError, pandera.errors.SchemaErrors)


class _ValidateLike(Protocol):
    """Any pandera schema: ``validate(df)`` raises on invalid data."""

    def validate(self, df: pl.DataFrame) -> object: ...


def as_predicate(schema: _ValidateLike) -> FailPredicate:
    """Return a ``DataFrame -> bool`` failure predicate for ``schema``.

    ``True`` while ``schema.validate(df)`` raises a schema error.  Any other
    exception -- a structural mismatch, a bug in the schema -- propagates
    unchanged rather than being swallowed as "does not fail".
    """

    def fails(df: pl.DataFrame) -> bool:
        try:
            schema.validate(df)
        except _SCHEMA_ERRORS:
            return True
        return False

    return fails


shrink_rows = make_shrink_rows(as_predicate)


__all__ = ["DEFAULT_MAX_EVALS", "FailPredicate", "Repro", "as_predicate", "shrink_rows"]
