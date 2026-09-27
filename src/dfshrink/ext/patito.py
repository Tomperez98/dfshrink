"""Adapter for `patito <https://patito.readthedocs.io/>`_ models.

A patito model validates by raising: ``Model.validate(df)`` returns the
validated frame when the data is valid and raises
:class:`patito.exceptions.DataFrameValidationError` when it is not.
``shrink_rows`` needs the *failure* predicate (``True`` while the frame is
invalid), so this module wraps ``validate`` and maps that error to ``True``.
``diagnose`` additionally reads the per-column error detail to report *why*
the frame fails.  patito does not expose which *rows* failed, so ``diagnose``
falls back to shrinking the full frame.

Requires the ``patito`` extra::

    uv sync --extra patito
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

try:
    import patito
except ImportError as exc:  # pragma: no cover - depends on install
    msg = (
        "dfshrink.ext.patito requires patito; install it with "
        "`uv sync --extra patito` (or `pip install 'dfshrink[patito]'`)"
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
    import polars as pl


class _ModelLike(Protocol):
    """A patito model class: classmethod ``validate`` raises on invalid data."""

    @classmethod
    def validate(cls, dataframe: pl.DataFrame) -> object: ...


def as_predicate(model: type[_ModelLike]) -> FailPredicate:
    """Return a ``DataFrame -> bool`` failure predicate for ``model``.

    ``True`` while ``model.validate(df)`` raises
    :class:`patito.exceptions.DataFrameValidationError`.  Any other exception --
    a structural mismatch, a bug in the model -- propagates unchanged rather
    than being swallowed as "does not fail".
    """

    def fails(df: pl.DataFrame) -> bool:
        try:
            model.validate(df)
        except patito.exceptions.DataFrameValidationError:
            return True
        return False

    return fails


def as_failure(model: type[_ModelLike]) -> Explainer:
    """Return a ``DataFrame -> Failure | None`` explainer for ``model``.

    Reads the first per-column error from the raised
    :class:`~patito.exceptions.DataFrameValidationError`: the error type stands
    in for the rule name, and the ``loc`` path names the column.  patito does
    not report which rows failed, so ``invalid_rows`` is always ``None``.
    """

    def explain(df: pl.DataFrame) -> Failure | None:
        try:
            model.validate(df)
        except patito.exceptions.DataFrameValidationError as exc:
            errors = exc.errors()
            column: str | None = None
            rule: str | None = None
            if errors:
                loc = errors[0].get("loc")
                if loc:
                    first = loc[0]
                    column = first if isinstance(first, str) else None
                rule = errors[0].get("type")
            return Failure(rule=rule, column=column, message=str(exc), invalid_rows=None)
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
