"""Drop the columns a failing frame does not need to keep failing.

:func:`dfshrink.shrink_rows` minimizes *rows*; :func:`dfshrink.minimize_values`
moves *values*; :func:`minimize_columns` removes whole *columns*.  The result is
the same failure on the narrowest frame: a schema that flags ``amount`` on a
frame carrying a debug column reduces to the columns the rule actually reads.

Column reduction is **schema-aware**, because a black-box ``DataFrame -> bool``
predicate cannot tell "still fails for the original reason" from "now fails
because a column went missing".  So the caller passes the adapter's *explainer*
(``as_failure(schema)``); a candidate column subset is accepted only while the
explainer still names the same rule and column.  That is the contract: the
frame must keep failing **for the same reason**, not merely keep failing.

The "frame must already match the schema's columns and dtypes" precondition
relaxes here: the reducer may **drop** columns, but never changes a kept
column's dtype.  ``minimality_proven`` spans two dimensions and both are
reported: :attr:`ColumnReduction.proven` is the column dimension, and
``repro.minimality_proven`` is the row dimension, re-checked against the
preserved reason so a column drop cannot make an inherited flag a lie.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, override

from dfshrink.failure import Diagnosis, Explainer, Failure
from dfshrink.shrink import DEFAULT_MAX_EVALS, Repro, _split, _without_row

if TYPE_CHECKING:
    from collections.abc import Sequence

    import polars as pl

__all__ = ["ColumnReduction", "minimize_columns"]


class _Exhausted:
    """Sentinel: the explainer budget is spent, so the reason is unknown."""


_EXHAUSTED = _Exhausted()


@dataclass(frozen=True, slots=True, eq=False)
class ColumnReduction:
    """A repro with the columns no failing rule needed removed.

    ``eq=False`` for the same reason as :class:`dfshrink.Repro`: a
    :class:`polars.DataFrame` field would otherwise compare element-wise.
    """

    repro: Repro
    """The column-reduced repro.  Its frame still fails for ``failure``'s reason,
    with the kept columns' dtypes and row order unchanged.  Its
    ``minimality_proven`` is the *row* dimension re-checked for that reason --
    not for the whole schema, which the reduced frame may no longer satisfy."""

    failure: Failure
    """The failure preserved across the reduction -- the reason the reduced
    frame still fails."""

    dropped_columns: tuple[str, ...]
    """The removed column names, in original frame order."""

    proven: bool
    """``True`` iff the kept column set is 1-minimal for the preserved reason:
    dropping any single remaining column changes or removes that reason."""

    predicate_calls: int
    """Explainer calls the column search spent (row shrinking did its own)."""

    @override
    def __repr__(self) -> str:
        """A compact repr: dropped count, width, and the proof flag."""
        state = "proven" if self.proven else "not proven"
        return (
            f"ColumnReduction(dropped={len(self.dropped_columns)}, "
            f"columns_left={self.repro.frame.width}, {state}, calls={self.predicate_calls})"
        )


def minimize_columns(
    source: Repro | Diagnosis,
    explain: Explainer,
    *,
    max_evals: int = DEFAULT_MAX_EVALS,
) -> ColumnReduction:
    """Remove every column the failing frame does not need to keep failing.

    ``explain`` is the adapter's failure explainer (``as_failure(schema)``):
    ``DataFrame -> Failure | None``.  ``source`` may be a
    :class:`~dfshrink.Diagnosis` or a bare :class:`~dfshrink.Repro`; its rows are
    kept and its frame defines the candidate columns.

    Contract:

    * Preconditions -- caller's bug, so panic: ``max_evals >= 1``; a source
      frame that fails; a failure the explainer can *name* (a structural
      failure with no rule is refused, because nothing can be preserved).
    * Postcondition: ``repro.frame`` is a column-subset of the input, keeps the
      input's rows and every kept column's dtype, and still fails for the
      preserved reason.
    * Expected failures, returned as values: an exhausted search budget returns
      the frame untouched with ``proven=False``; it never guesses.

    The search is ddmin over columns, so it reaches 1-minimality in roughly
    ``O(k log k)`` explainer calls for ``k`` columns.  A column is removed only
    while ``explain`` still reports the *same* rule and column; a drop that
    merely breaks the frame some other way (a missing required column) is
    rejected.  The column search gets its own ``max_evals`` budget; naming the
    source reason is setup and always fits (``max_evals >= 1``).
    """
    if max_evals < 1:
        msg = f"max_evals must be >= 1, got {max_evals}"
        raise ValueError(msg)

    repro = source.repro if isinstance(source, Diagnosis) else source
    frame = repro.frame

    tracker = _ReasonTracker(frame, explain, max_evals)
    baseline = tracker.explain(frame)
    assert not isinstance(baseline, _Exhausted), "max_evals >= 1 leaves room for the baseline"
    if baseline is None:
        msg = "minimize_columns needs a failing frame; the source repro passes"
        raise ValueError(msg)
    if baseline.rule is None:
        msg = (
            "minimize_columns needs a named failing rule; the validator reported a "
            "structural failure (missing column or wrong dtype) with no rule to preserve"
        )
        raise ValueError(msg)

    current = tuple(range(frame.width))
    tracker.last_true = current
    if frame.width >= 2:
        n = 2
        while len(current) >= 2 and not tracker.exhausted:
            reduced, n = _reduce_once(tracker, current, n, baseline)
            if reduced is not None:
                current = reduced
                continue
            if n >= len(current):
                break
            n = min(len(current), 2 * n)
    assert current == tracker.last_true, "postcondition: reduced columns must still fail"

    reduced_frame = frame.select([frame.columns[i] for i in current])
    rows_proven = repro.minimality_proven and _rows_minimal(reduced_frame, tracker, baseline)
    dropped = tuple(name for i, name in enumerate(frame.columns) if i not in set(current))
    return ColumnReduction(
        repro=replace(repro, frame=reduced_frame, minimality_proven=rows_proven),
        failure=baseline,
        dropped_columns=dropped,
        proven=frame.width < 2 or not tracker.exhausted,
        predicate_calls=tracker.calls,
    )


def _reduce_once(
    tracker: _ReasonTracker,
    current: tuple[int, ...],
    n: int,
    reason: Failure,
) -> tuple[tuple[int, ...] | None, int]:
    """One ddmin step over columns: prefer a same-reason chunk, then a complement.

    Returns the reduced index tuple (or ``None`` when neither a chunk nor a
    complement keeps the reason) and the chunk count to use next.
    """
    chunks = _split(current, n)
    for _, _, chunk in chunks:
        if tracker.holds_on(chunk, reason) is True:
            return chunk, 2
    for start, stop, _ in chunks:
        complement = current[:start] + current[stop:]
        if complement and tracker.holds_on(complement, reason) is True:
            return complement, max(n - 1, 2)
    return None, n


def _rows_minimal(frame: pl.DataFrame, tracker: _ReasonTracker, reason: Failure) -> bool:
    """Re-check 1-minimality along rows against the preserved reason.

    Mirrors :func:`dfshrink.shrink_rows`: a one-row frame is trivially minimal
    (the empty candidate is never tested), and a row that can be dropped while
    the reason survives means the inherited flag is no longer true.  Returns
    ``False`` when the budget runs out before a row is cleared.
    """
    if frame.height < 2:
        return True
    for row in range(frame.height):
        if tracker.same_reason(_without_row(frame, row), reason) is not False:
            return False
    return True


class _ReasonTracker:
    """Budgeted explainer that answers "same failing reason?" over column subsets.

    Three-state: :meth:`same_reason` returns ``True`` (same rule and column),
    ``False`` (a different or absent failure), or ``None`` once the budget is
    spent.  ``None`` is never read as either side -- the search stops and the
    result is reported unproven.
    """

    def __init__(self, frame: pl.DataFrame, explain: Explainer, max_evals: int) -> None:
        self._frame = frame
        self._explain = explain
        self.max_evals = max_evals
        self.calls = 0
        self.last_true: tuple[int, ...] | None = None

    @property
    def exhausted(self) -> bool:
        """``True`` once no further explainer call may be made."""
        return self.calls >= self.max_evals

    def explain(self, frame: pl.DataFrame) -> Failure | _Exhausted | None:
        """Explain ``frame``, or return :data:`_EXHAUSTED` when the budget is spent."""
        if self.exhausted:
            return _EXHAUSTED
        self.calls += 1
        return self._explain(frame)

    def same_reason(self, frame: pl.DataFrame, reason: Failure) -> bool | None:
        """Whether ``frame`` still fails for ``reason`` (same rule and column)."""
        found = self.explain(frame)
        if isinstance(found, _Exhausted):
            return None
        return found is not None and found.rule == reason.rule and found.column == reason.column

    def holds_on(self, columns: Sequence[int], reason: Failure) -> bool | None:
        """Whether selecting ``columns`` still fails for ``reason``."""
        candidate = self._frame.select([self._frame.columns[i] for i in columns])
        outcome = self.same_reason(candidate, reason)
        if outcome is True:
            self.last_true = tuple(columns)
        return outcome
