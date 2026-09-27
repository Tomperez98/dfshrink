"""Shared plumbing for the per-library adapters in :mod:`pycheck.ext`.

Every adapter module turns one validator's failure signal into a
``DataFrame -> bool`` predicate and hands it to :func:`pycheck.shrink_rows`.
The predicate is library-specific; the shrink call is not.  Adapters build
their public ``shrink_rows`` from :func:`make_shrink_rows`, so the wrapper --
including the keyword-only ``max_evals`` and its default -- is written once and
cannot drift between libraries.  The same adapters build ``diagnose`` from
:func:`make_diagnose`: it explains *why* the frame fails (rule, column, invalid
rows) and shrinks -- using the invalid rows as the starting point when the
validator reports them, the full frame otherwise.

This module imports no validator library; the adapters own those imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pycheck.failure import Diagnosis, Explainer, Failure
from pycheck.shrink import (
    DEFAULT_MAX_EVALS,
    FailPredicate,
    Repro,
    shrink_rows as _shrink_rows,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    import polars as pl

__all__ = [
    "DEFAULT_MAX_EVALS",
    "Diagnose",
    "Diagnosis",
    "Explainer",
    "FailPredicate",
    "Failure",
    "Repro",
    "ShrinkRows",
    "make_diagnose",
    "make_shrink_rows",
]


class ShrinkRows[SchemaT](Protocol):
    """A schema-aware :func:`pycheck.shrink_rows` bound to one library's predicate."""

    def __call__(
        self,
        frame: pl.DataFrame,
        schema: SchemaT,
        *,
        max_evals: int = DEFAULT_MAX_EVALS,
    ) -> Repro | None: ...


class Diagnose[SchemaT](Protocol):
    """A schema-aware :func:`pycheck.ext.<lib>.diagnose` bound to one library."""

    def __call__(
        self,
        frame: pl.DataFrame,
        schema: SchemaT,
        *,
        max_evals: int = DEFAULT_MAX_EVALS,
    ) -> Diagnosis | None: ...


def make_shrink_rows[SchemaT](
    as_predicate: Callable[[SchemaT], FailPredicate],
) -> ShrinkRows[SchemaT]:
    """Build the ``shrink_rows(frame, schema, *, max_evals)`` wrapper for an adapter.

    ``as_predicate`` maps a library schema to the failure predicate
    :func:`pycheck.shrink_rows` minimizes; the returned callable re-applies it
    on each invocation.  See :func:`pycheck.shrink_rows` for the full contract.
    """

    def shrink_rows(
        frame: pl.DataFrame,
        schema: SchemaT,
        *,
        max_evals: int = DEFAULT_MAX_EVALS,
    ) -> Repro | None:
        """Shrink ``frame`` to a minimal row subset that still fails ``schema``.

        A thin wrapper over :func:`pycheck.shrink_rows`; see there for the full
        contract.
        """
        return _shrink_rows(frame, as_predicate(schema), max_evals=max_evals)

    return shrink_rows


def make_diagnose[SchemaT](
    as_failure: Callable[[SchemaT], Explainer],
    as_predicate: Callable[[SchemaT], FailPredicate],
) -> Diagnose[SchemaT]:
    """Build the ``diagnose(frame, schema, *, max_evals)`` wrapper for an adapter.

    ``as_failure`` maps a schema to its failure explainer (``DataFrame ->
    Failure | None``); ``as_predicate`` maps it to the failure predicate
    :func:`pycheck.shrink_rows` minimizes.  ``diagnose`` explains first and
    shrinks second: when the explainer reports the invalid rows, shrinking
    starts there instead of over the whole frame, so the validator's own
    failure signal -- not black-box ddmin -- pinpoints the repro.

    Contract (same shape as :func:`pycheck.shrink_rows`):

    * Preconditions -- caller's bug, so panic: an empty ``frame`` or
      ``max_evals < 1`` raises ``ValueError``.
    * Expected failure, returned as a value: a non-failing frame returns
      ``None``; otherwise a :class:`Diagnosis` whose ``repro`` still fails,
      has >= 1 row, preserves order, and is 1-minimal when
      ``minimality_proven`` is ``True``.
    * A validator that reports a failure the predicate does not reproduce is
      an adapter bug and panics.
    """

    def diagnose(
        frame: pl.DataFrame,
        schema: SchemaT,
        *,
        max_evals: int = DEFAULT_MAX_EVALS,
    ) -> Diagnosis | None:
        """Explain and shrink ``frame`` against ``schema``.

        Returns ``None`` when the frame passes, else a :class:`Diagnosis` with
        the minimal failing repro and the reason it fails (when the validator
        exposes one).  See :func:`pycheck.shrink_rows` for the repro contract.
        """
        if frame.height < 1:
            msg = f"frame must have at least one row, got {frame.height}"
            raise ValueError(msg)
        if max_evals < 1:
            msg = f"max_evals must be >= 1, got {max_evals}"
            raise ValueError(msg)

        failure = as_failure(schema)(frame)
        if failure is None:
            return None

        start = frame if failure.invalid_rows is None else failure.invalid_rows
        repro = _shrink_rows(start, as_predicate(schema), max_evals=max_evals)
        assert repro is not None, (
            "diagnose: the validator reported a failure the predicate does not reproduce"
        )
        return Diagnosis(repro=repro, failure=failure)

    return diagnose
