"""Adapter for `patito <https://patito.readthedocs.io/>`_ models.

A patito model validates by raising: ``Model.validate(df)`` returns the
validated frame when the data is valid and raises
:class:`patito.exceptions.DataFrameValidationError` when it is not.
``shrink_rows`` needs the *failure* predicate (``True`` while the frame is
invalid), so this module wraps ``validate`` and maps that error to ``True``.

Requires the ``patito`` extra::

    uv sync --extra patito
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

try:
    import patito
except ImportError as exc:  # pragma: no cover - depends on install
    msg = (
        "pycheck.ext.patito requires patito; install it with "
        "`uv sync --extra patito` (or `pip install 'pycheck[patito]'`)"
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


shrink_rows = make_shrink_rows(as_predicate)


__all__ = ["DEFAULT_MAX_EVALS", "FailPredicate", "Repro", "as_predicate", "shrink_rows"]
