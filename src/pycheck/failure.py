"""Structured failure metadata, and the diagnosis it powers.

:class:`Failure` is *why* a frame failed a validator -- the rule, the column,
and, when the validator can say, the rows that did it.  :class:`Diagnosis`
pairs a minimal failing repro with that reason, so "here is a failing frame"
becomes "column ``amount`` fails rule ``min``, and here is one row that does
it".

These types are validator-agnostic: :mod:`pycheck` imports no validation
library.  The per-library adapters in :mod:`pycheck.ext` build them, and
:func:`pycheck.ext.<lib>.diagnose` returns them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import polars as pl

from pycheck._render import describe_failure, render_diagnosis_markdown

if TYPE_CHECKING:
    from pycheck.shrink import Repro

type Explainer = Callable[[pl.DataFrame], Failure | None]
"""A ``DataFrame -> Failure | None`` callable: ``None`` while the frame passes,
a :class:`Failure` while it fails.  Built per-library by ``as_failure``."""


@dataclass(frozen=True, slots=True, eq=False)
class Failure:
    """Why a frame failed, as the validator reported it.

    ``eq=False`` for the same reason as :class:`pycheck.Repro`: a
    :class:`polars.DataFrame` field would otherwise compare element-wise and
    yield a frame, not a bool.
    """

    rule: str | None
    """The failing rule/check, as the validator names it (e.g. ``"amount|min"``,
    ``"greater_than(0)"``).  ``None`` when the validator gives no rule name."""

    column: str | None
    """The column the rule is about, when the validator attributes it to one.
    ``None`` for dataframe-level rules, or validators that do not say."""

    message: str | None
    """The validator's own human-readable message, when it produces one."""

    invalid_rows: pl.DataFrame | None
    """The rows the validator already flagged as invalid, if it exposes them.

    ``None`` when the validator does not report which rows failed, or when the
    failure is structural (missing column / wrong dtype) rather than row
    content.  When set, it is a non-empty, order-preserving subsequence of the
    input."""

    @override
    def __repr__(self) -> str:
        """A compact repr: the invalid row count, never the frame itself."""
        rows = "None" if self.invalid_rows is None else f"<{self.invalid_rows.height} rows>"
        return (
            f"Failure(rule={self.rule!r}, column={self.column!r}, "
            f"message={self.message!r}, invalid_rows={rows})"
        )


@dataclass(frozen=True, slots=True, eq=False)
class Diagnosis:
    """A minimal failing repro plus the reason it fails."""

    repro: Repro
    """The reduced frame that still fails (see :func:`pycheck.shrink_rows`)."""

    failure: Failure | None
    """Why it fails, when the validator exposed failure metadata."""

    def to_markdown(self) -> str:
        """A ticket-ready report: why it failed, then the minimal repro table."""
        return render_diagnosis_markdown(self)

    @override
    def __str__(self) -> str:
        """A one-line summary: the failing rule/column, then the repro shape."""
        return f"Diagnosis({describe_failure(self.failure)}; {self.repro!s})"

    @override
    def __repr__(self) -> str:
        """A constructor-shaped repr; delegates the frame to :class:`Repro`."""
        return f"Diagnosis(failure={self.failure!r}, repro={self.repro!r})"


__all__ = ["Diagnosis", "Explainer", "Failure"]
