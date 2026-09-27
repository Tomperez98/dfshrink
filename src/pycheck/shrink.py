"""Minimal failing-frame shrinking for Polars.

The core operation is :func:`shrink_rows`::

    shrink_rows(frame, fails, *, max_evals=...) -> Repro | None

Given a frame and a predicate that reports whether the failure is present, it
returns the smallest subset of rows that still reproduces the failure.

Contract
--------

Preconditions (a violation is the caller's bug, so we panic with an explicit
``raise`` -- never an ``assert``, which ``python -O`` strips):

* ``frame`` is a :class:`polars.DataFrame` with at least one row.  An empty
  frame is rejected (``ValueError``) rather than silently accepted as a
  "minimal" repro.
* ``max_evals >= 1`` (``ValueError`` otherwise).
* ``fails`` is a *total* function ``DataFrame -> bool``.  Returning ``None``
  is a predicate bug and raises ``TypeError``; any other exception propagates
  unchanged and is never swallowed as "does not fail" (see WRITE rule 2 --
  never drop a failure).

Postconditions (a violation is our bug, so we panic):

* ``None`` is returned **iff** ``fails(frame)`` is ``False``.
* ``Repro.frame`` satisfies ``fails(Repro.frame) is True``.
* ``Repro.frame`` has at least one row and preserves the relative order of the
  original rows (a subsequence, not a reordering).
* When ``Repro.minimality_proven`` is ``True``, the result is *1-minimal*:
  removing any single remaining row makes ``fails`` return ``False``.

Expected failures (returned as values, not crashes):

* The input frame does not fail -> ``None``.
* The evaluation budget runs out -> a ``Repro`` with
  ``minimality_proven=False``.  The frame still reproduces the failure, but
  1-minimality was not established.

The algorithm is ddmin (Zeller & Hildebrandt, *Simplifying and Isolating
Failure-Inducing Input*, IEEE TSE 2002), which reaches 1-minimality in roughly
``O(n log n)`` predicate calls instead of the ``O(n^2)`` of greedy removal.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import override

import polars as pl

from pycheck._render import render_code, render_markdown

DEFAULT_MAX_EVALS = 10_000
"""Default cap on predicate calls; bounds every ``shrink_rows`` invocation."""

type FailPredicate = Callable[[pl.DataFrame], bool]
"""The predicate :func:`shrink_rows` minimizes: ``True`` while the failure is present."""

type _Chunk = tuple[int, int, tuple[int, ...]]
"""A contiguous slice of a candidate: ``(start, stop, rows[start:stop])``."""


@dataclass(frozen=True, slots=True, eq=False)
class Repro:
    """A frame that still reproduces a failure, reduced as far as the budget allowed.

    ``eq=False`` on purpose: :class:`polars.DataFrame` equality is
    element-wise, so a generated dataclass ``__eq__`` would compare frames into
    a frame and return something that is not a ``bool``.
    """

    frame: pl.DataFrame
    """The reduced frame.  Post: satisfies the predicate; >= 1 row; subsequence order."""
    original_rows: int
    """Row count of the input frame, for reporting how much was removed."""
    predicate_calls: int
    """Number of ``fails`` evaluations spent."""
    minimality_proven: bool
    """``True`` iff the result was proven 1-minimal within the budget."""

    @property
    def removed_rows(self) -> int:
        """Rows dropped from the input frame."""
        return self.original_rows - self.frame.height

    def as_frame(self) -> pl.DataFrame:
        """The reduced frame -- the replayable repro to re-run the predicate on."""
        return self.frame

    def to_code(self) -> str:
        """A pasteable ``pl.DataFrame(...)`` constructor for the repro.

        ``eval`` of the result, with ``polars as pl`` in scope, rebuilds an
        equal frame.  A dtype that cannot be rendered without loss raises
        ``TypeError`` instead of emitting code that builds a different frame.
        """
        return render_code(self.frame)

    def to_markdown(self) -> str:
        """The repro as a GitHub-flavoured markdown table (dtypes in headers)."""
        return render_markdown(self.frame)

    @override
    def __str__(self) -> str:
        """A one-line summary: size, rows removed, calls, and minimality."""
        rows = "row" if self.frame.height == 1 else "rows"
        proven = "proven" if self.minimality_proven else "not proven"
        return (
            f"Repro({self.frame.height} {rows}, removed {self.removed_rows} of "
            f"{self.original_rows}, {self.predicate_calls} predicate calls, "
            f"minimality {proven})"
        )

    @override
    def __repr__(self) -> str:
        """A constructor-shaped repr that never dumps the frame."""
        return (
            f"Repro(rows={self.frame.height}, removed_rows={self.removed_rows}, "
            f"predicate_calls={self.predicate_calls}, "
            f"minimality_proven={self.minimality_proven})"
        )


def shrink_rows(
    frame: pl.DataFrame,
    fails: FailPredicate,
    *,
    max_evals: int = DEFAULT_MAX_EVALS,
) -> Repro | None:
    """Reduce ``frame`` to a 1-minimal row subset that still satisfies ``fails``.

    ``fails`` is a predicate ``DataFrame -> bool`` reporting whether the
    failure is present.  To shrink against a validator instead, pass its
    ``.is_valid`` / ``.validate`` through the matching adapter in
    :mod:`pycheck.ext` (``pycheck.ext.dataframely``, ``pycheck.ext.pandera``)
    -- so ``shrink_rows(df, schema_predicate)`` just works.

    Returns ``None`` when the input frame does not fail.  See the module
    docstring for the full contract.
    """
    if frame.height < 1:
        msg = f"frame must have at least one row, got {frame.height}"
        raise ValueError(msg)
    if max_evals < 1:
        msg = f"max_evals must be >= 1, got {max_evals}"
        raise ValueError(msg)

    tracker = _PredicateTracker(frame, fails, max_evals)
    current = tuple(range(frame.height))
    if not tracker.holds_on(current):
        return None

    n = 2
    while len(current) >= 2 and not tracker.exhausted:
        reduced, n = _reduce_once(tracker, current, n)
        if reduced is not None:
            current = reduced
            continue
        if n >= len(current):
            break
        n = min(len(current), 2 * n)

    assert tracker.proven_holds(current), "postcondition: reduced frame must fail"
    return Repro(
        frame=_take_rows(frame, current),
        original_rows=frame.height,
        predicate_calls=tracker.calls,
        minimality_proven=not tracker.exhausted,
    )


def _reduce_once(
    tracker: _PredicateTracker,
    current: tuple[int, ...],
    n: int,
) -> tuple[tuple[int, ...] | None, int]:
    """One ddmin step: prefer a failing chunk, then a failing complement.

    Returns the reduced index tuple (or ``None`` when neither a chunk nor a
    complement fails) and the chunk count to use next.
    """
    chunks = _split(current, n)
    for _, _, chunk in chunks:
        if tracker.holds_on(chunk):
            return chunk, 2
    for start, stop, _ in chunks:
        # Chunks partition ``current`` contiguously, so a chunk's complement is
        # the two outer slices of ``current`` -- no set membership scan.
        complement = current[:start] + current[stop:]
        if complement and tracker.holds_on(complement):
            return complement, max(n - 1, 2)
    return None, n


def _split(rows: tuple[int, ...], n: int) -> tuple[_Chunk, ...]:
    """Partition ``rows`` into at most ``n`` contiguous, near-equal chunks.

    Each chunk carries the half-open ``(start, stop)`` bounds of its slice of
    ``rows``, so a chunk's complement can be built by slicing ``rows`` instead
    of scanning it for set membership.
    """
    size, extra = divmod(len(rows), n)
    chunks: list[_Chunk] = []
    start = 0
    for i in range(n):
        stop = start + size + (1 if i < extra else 0)
        if stop > start:
            chunks.append((start, stop, rows[start:stop]))
        start = stop
    return tuple(chunks)


def _take_rows(frame: pl.DataFrame, rows: tuple[int, ...]) -> pl.DataFrame:
    """Select rows by position.  ``rows`` is ascending, so order is preserved."""
    return frame[list(rows)]


class _PredicateTracker:
    """Budgeted ``fails`` evaluator over row-index subsets.

    Invariant: once :attr:`exhausted` is ``True`` it stays ``True`` and no
    further predicate call is made.  A candidate arriving after exhaustion is
    reported as *not failing*, which is conservative -- it can only leave the
    current candidate unchanged, never select an untested one.

    ddmin never re-tests a subset (every candidate is strictly smaller than
    the last successful one), so there is no memoisation: each call is a fresh
    ``fails`` evaluation.
    """

    def __init__(
        self,
        frame: pl.DataFrame,
        fails: FailPredicate,
        max_evals: int,
    ) -> None:
        self._frame = frame
        self._fails = fails
        self._max_evals = max_evals
        self.calls = 0
        self.exhausted = False
        self._last_true: tuple[int, ...] | None = None

    def holds_on(self, rows: Sequence[int]) -> bool:
        """Return whether ``rows`` still fail, within the budget.

        A truthy non-``bool`` return is coerced with ``bool()``; returning
        ``None`` is a predicate bug and panics rather than reading as a miss.
        """
        if self.calls >= self._max_evals:
            self.exhausted = True
            return False
        self.calls += 1
        result = self._fails(self._frame[list(rows)])
        if result is None:
            msg = "fails returned None; the contract requires a bool"
            raise TypeError(msg)
        value = bool(result)
        if value:
            self._last_true = tuple(rows)
        return value

    def proven_holds(self, rows: Sequence[int]) -> bool:
        """Invariant check: ``rows`` is the candidate that last satisfied ``fails``."""
        assert tuple(rows) == self._last_true, "invariant: candidate does not hold"
        return True
