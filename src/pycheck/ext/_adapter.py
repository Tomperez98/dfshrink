"""Shared plumbing for the per-library adapters in :mod:`pycheck.ext`.

Every adapter module turns one validator's failure signal into a
``DataFrame -> bool`` predicate and hands it to :func:`pycheck.shrink_rows`.
The predicate is library-specific; the shrink call is not.  Adapters build
their public ``shrink_rows`` from :func:`make_shrink_rows`, so the wrapper --
including the keyword-only ``max_evals`` and its default -- is written once and
cannot drift between libraries.

This module imports no validator library; the adapters own those imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

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
    "FailPredicate",
    "Repro",
    "ShrinkRows",
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
