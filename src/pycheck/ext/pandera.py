"""Adapter for `pandera <https://pandera.readthedocs.io/>`_ schemas.

A pandera schema validates by raising: ``validate(df)`` returns normally when
the frame is valid and raises a :class:`pandera.errors.SchemaError` (or
:class:`~pandera.errors.SchemaErrors`) when it is not.  ``shrink_rows`` needs
the *failure* predicate (``True`` while the frame is invalid), so this module
wraps ``validate`` and maps its schema errors to ``True``.  ``diagnose``
additionally reads the failure cases -- the failing column, check, and row
indices -- to report *why* the frame fails.

Requires the ``pandera`` extra::

    uv sync --extra pandera
"""

from __future__ import annotations

from typing import Protocol

import polars as pl

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
    Diagnosis,
    Explainer,
    FailPredicate,
    Failure,
    Repro,
    make_diagnose,
    make_shrink_rows,
)

# DataFrameModel.validate raises SchemaError; DataFrameSchema.validate raises
# SchemaErrors.  Both are the "data is invalid" signal, not a schema bug.
_SCHEMA_ERRORS = (pandera.errors.SchemaError, pandera.errors.SchemaErrors)


class _ValidateLike(Protocol):
    """Any pandera schema: ``validate(df)`` raises on invalid data."""

    def validate(self, df: pl.DataFrame) -> object: ...


class _LazyValidateLike(Protocol):
    """Any pandera schema: ``validate(df, lazy=True)`` raises on invalid data."""

    def validate(self, df: pl.DataFrame, *, lazy: bool = ...) -> object: ...


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


def _error_message(exc: pandera.errors.SchemaError | pandera.errors.SchemaErrors) -> str | None:
    """The first human-readable ``error`` string, without the query-plan dump."""
    message = getattr(exc, "message", None)
    if message is None:  # eager SchemaError carries no .message dict
        return str(exc)
    for section in message.values():
        for entries in section.values():
            for entry in entries:
                error = entry.get("error")
                return error if isinstance(error, str) else None
    return None


def as_failure(schema: _LazyValidateLike) -> Explainer:
    """Return a ``DataFrame -> Failure | None`` explainer for ``schema``.

    Validates lazily so all failures are collected, then reads the failing
    column, check, and row indices from ``SchemaErrors.failure_cases``.  A
    schema-level failure (missing column, wrong dtype) has no row indices and
    is reported with ``invalid_rows=None``.
    """

    def explain(df: pl.DataFrame) -> Failure | None:
        try:
            schema.validate(df, lazy=True)
        except _SCHEMA_ERRORS as exc:
            cases = getattr(exc, "failure_cases", None)
            indexed = None if cases is None else cases.filter(pl.col("index").is_not_null())
            if indexed is not None and indexed.height > 0:
                indices = sorted(set(indexed["index"].to_list()))
                return Failure(
                    rule=indexed["check"][0],
                    column=indexed["column"][0],
                    message=_error_message(exc),
                    invalid_rows=df[indices],
                )
            return Failure(rule=None, column=None, message=_error_message(exc), invalid_rows=None)
        return None

    return explain


shrink_rows = make_shrink_rows(as_predicate)
diagnose = make_diagnose(as_failure, as_predicate)


__all__ = [
    "DEFAULT_MAX_EVALS",
    "Diagnosis",
    "FailPredicate",
    "Failure",
    "Repro",
    "as_failure",
    "as_predicate",
    "diagnose",
    "shrink_rows",
]
