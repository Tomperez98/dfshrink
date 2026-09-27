"""Adapter for `dataframely <https://github.com/quantco/dataframely>`_ schemas.

A dataframely schema exposes ``is_valid(df) -> bool``: ``True`` when the frame
is valid.  ``shrink_rows`` needs the *failure* predicate (``True`` while the
frame is invalid), so this module inverts it.  ``diagnose`` additionally uses
``Schema.filter`` to report *why* the frame fails -- the rule, the column, and
the invalid rows -- instead of only that it does.

Requires the ``dataframely`` extra::

    uv sync --extra dataframely
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import dataframely.exc as _dy_exc
except ImportError as exc:  # pragma: no cover - depends on install
    msg = (
        "dfshrink.ext.dataframely requires dataframely; install it with "
        "`uv sync --extra dataframely` (or `pip install 'dfshrink[dataframely]'`)"
    )
    raise ImportError(msg) from exc

from dfshrink.ext._adapter import (
    DEFAULT_MAX_EVALS,
    Diagnosis,
    Explainer,
    FailPredicate,
    Failure,
    Repro,
    make_diagnose,
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


def _rule_column(rule: str) -> str | None:
    """Best-effort column for a dataframely rule key like ``"amount|min"``.

    dataframely names column rules ``column|rule`` and dataframe-level
    ``@dy.rule()`` methods by a bare name, so the column is the prefix before
    the first ``|`` when one is present, else ``None``.
    """
    column, sep, _ = rule.partition("|")
    return column if sep else None


def as_failure(schema: type[dy.Schema]) -> Explainer:
    """Return a ``DataFrame -> Failure | None`` explainer for ``schema``.

    Uses ``Schema.filter``, which splits the frame into valid and invalid rows
    and reports per-rule failure counts.  The rule with the most failures is
    reported, along with its column and the invalid rows themselves.

    A structural mismatch (missing column or wrong dtype) makes ``filter``
    raise ``SchemaError``; that is reported as a :class:`Failure` with no
    ``invalid_rows`` -- the frame fails, but not by row content.
    """

    def explain(df: pl.DataFrame) -> Failure | None:
        try:
            result = schema.filter(df)
        except _dy_exc.SchemaError as exc:
            return Failure(rule=None, column=None, message=str(exc), invalid_rows=None)
        counts = result.failure.counts()
        if not counts:
            return None
        rule = max(counts, key=lambda name: counts[name])
        return Failure(
            rule=rule,
            column=_rule_column(rule),
            message=None,
            invalid_rows=result.failure.invalid(),
        )

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
