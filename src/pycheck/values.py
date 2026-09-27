"""Pull a failing cell to the boundary where its rule starts to hold.

:func:`pycheck.shrink_rows` drops rows; :func:`minimize_values` keeps them and
pushes the flagged column's values to the edge of the failing region.  Under a
``min=0`` rule a ``-9`` becomes ``-1`` -- the last value that still fails, and so
the smallest repro of the *value*, not just of the rows.

The search is a bracket-and-bisect over one column: exponential steps find a
passing value in the chosen direction, then bisection closes on the failing value
adjacent to it.  It assumes the predicate is **monotone along that column** --
exactly one crossing, passing beyond it.  When no crossing is found, or the
budget runs out, the value is left untouched and ``proven`` is ``False``: the
step never guesses a boundary it could not show.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from typing import Any, Literal, override

import polars as pl

from pycheck.failure import Diagnosis
from pycheck.shrink import DEFAULT_MAX_EVALS, FailPredicate, Repro

type Direction = Literal["increase", "decrease"]
"""Which way to move a value, toward the region where the rule holds."""

_INCREASE_HINTS = ("min", "greater", "positive", "above", "at_least")
_DECREASE_HINTS = ("max", "less", "negative", "below", "at_most")
_INCREASE_EXACT = frozenset({"ge", "gt", "gte", ">=", ">"})
_DECREASE_EXACT = frozenset({"le", "lt", "lte", "<=", "<"})

_INT_BITS: dict[str, tuple[int, bool]] = {
    "Int8": (8, True),
    "Int16": (16, True),
    "Int32": (32, True),
    "Int64": (64, True),
    "Int128": (128, True),
    "UInt8": (8, False),
    "UInt16": (16, False),
    "UInt32": (32, False),
    "UInt64": (64, False),
    "UInt128": (128, False),
}

_FLOAT_LIMIT = sys.float_info.max
"""Cap for a Float64 bracket; a predicate still failing here reports unproven."""


def direction_for_rule(rule: str | None) -> Direction | None:
    """The direction an ``increase``/``decrease`` search moves, from a rule name.

    Best-effort and deliberately conservative: ``min``/``greater``/``positive``
    style names mean the failing values are *below* the valid region, so the
    search moves **increase**; ``max``/``less``/``negative`` names move
    **decrease**.  ``None`` when the name is unknown, so the caller decides
    rather than the function guessing.
    """
    if rule is None:
        return None
    lowered = rule.lower()
    name = lowered.rsplit("|", 1)[-1].split("(", 1)[0].strip()
    if name in _INCREASE_EXACT or any(hint in lowered for hint in _INCREASE_HINTS):
        return "increase"
    if name in _DECREASE_EXACT or any(hint in lowered for hint in _DECREASE_HINTS):
        return "decrease"
    return None


@dataclass(frozen=True, slots=True, eq=False)
class ValueReduction:
    """A repro whose flagged column values sit on the failing boundary."""

    repro: Repro
    """The value-minimized repro: same rows, boundary values.  ``frame`` still fails."""

    column: str
    """The column that was minimized."""

    direction: Direction
    """Which way values moved toward the valid region."""

    proven: bool
    """``True`` iff every cell reached the failing value adjacent to passing.

    ``False`` when no crossing was found (the predicate is not monotone along
    the column, or the budget ran out); the untouched original is returned rather
    than a guessed boundary.
    """

    predicate_calls: int
    """Predicate calls spent on the value search (row shrinking did its own)."""

    @override
    def __repr__(self) -> str:
        state = "proven" if self.proven else "not proven"
        return (
            f"ValueReduction(column={self.column!r}, direction={self.direction!r}, "
            f"{state}, calls={self.predicate_calls})"
        )


def minimize_values(
    source: Repro | Diagnosis,
    fails: FailPredicate,
    *,
    column: str | None = None,
    direction: Direction | None = None,
    max_evals: int = DEFAULT_MAX_EVALS,
) -> ValueReduction:
    """Move the flagged column's values to the failing boundary.

    ``fails`` is the same failure predicate used for shrinking.  ``source`` may
    be a :class:`~pycheck.Diagnosis` (then ``column`` and the rule that picks the
    direction come from its ``failure``) or a bare :class:`~pycheck.Repro` (then
    pass ``column`` and either ``direction`` or a rule-derived direction).

    Contract:

    * Preconditions -- caller's bug, so panic: ``max_evals >= 1``; a known
      ``column`` present in the frame; a ``direction`` (explicitly or from a
      recognizable rule name); a numeric, non-null cell to move.
    * Postcondition: ``ValueReduction.repro.frame`` still satisfies ``fails``;
      ``proven`` is ``True`` iff every cell reached the failing value adjacent to
      the passing region within the budget.
    * Expected failure, returned as a value: no crossing found or budget
      exhausted leaves the cell untouched and reports ``proven=False``.
    """
    if max_evals < 1:
        msg = f"max_evals must be >= 1, got {max_evals}"
        raise ValueError(msg)

    repro, rule = _source_parts(source)
    target = column if column is not None else _source_column(source)
    if target is None:
        msg = "minimize_values needs a column; pass column=... or a Diagnosis with failure.column"
        raise ValueError(msg)
    if target not in repro.frame.columns:
        msg = f"column {target!r} is not in the frame"
        raise ValueError(msg)

    resolved = direction if direction is not None else direction_for_rule(rule)
    if resolved not in ("increase", "decrease"):
        msg = "minimize_values needs a direction; pass direction=... or a rule with a known name"
        raise ValueError(msg)

    dtype = repro.frame[target].dtype
    bounds = _bounds(dtype)
    tracker = _Tracker(fails, max_evals)
    frame = repro.frame
    proven = True
    for row in range(frame.height):
        frame, cell_proven = _minimize_cell(
            frame, tracker, column=target, row=row, direction=resolved, dtype=dtype, bounds=bounds
        )
        if not cell_proven:
            proven = False
            break

    row_proven = repro.minimality_proven and proven and _rows_still_minimal(frame, tracker)
    return ValueReduction(
        repro=replace(repro, frame=frame, minimality_proven=row_proven),
        column=target,
        direction=resolved,
        proven=proven,
        predicate_calls=tracker.calls,
    )


def _source_parts(source: Repro | Diagnosis) -> tuple[Repro, str | None]:
    if isinstance(source, Diagnosis):
        failure = source.failure
        return source.repro, None if failure is None else failure.rule
    return source, None


def _source_column(source: Repro | Diagnosis) -> str | None:
    if isinstance(source, Diagnosis) and source.failure is not None:
        return source.failure.column
    return None


def _minimize_cell(
    frame: pl.DataFrame,
    tracker: _Tracker,
    *,
    column: str,
    row: int,
    direction: Direction,
    dtype: pl.DataType,
    bounds: tuple[int, int] | None,
) -> tuple[pl.DataFrame, bool]:
    original = frame[column][row]
    if original is None:
        msg = "cannot minimize a null cell; the failure is the null, not the value"
        raise ValueError(msg)
    if isinstance(original, float) and not math.isfinite(original):
        msg = "cannot minimize a non-finite cell; a nan or inf has no boundary"
        raise ValueError(msg)

    bracket = _bracket(
        frame,
        tracker,
        column=column,
        row=row,
        original=original,
        direction=direction,
        dtype=dtype,
        bounds=bounds,
    )
    if bracket is None:
        return frame, False

    failing, passing = bracket
    value, found = _bisect(
        frame,
        tracker,
        column=column,
        row=row,
        failing=failing,
        passing=passing,
        bounds=bounds,
        dtype=dtype,
    )
    return _with_cell(frame, column, row, value, dtype), found


def _bracket(
    frame: pl.DataFrame,
    tracker: _Tracker,
    *,
    column: str,
    row: int,
    original: float,
    direction: Direction,
    dtype: pl.DataType,
    bounds: tuple[int, int] | None,
) -> tuple[int | float, int | float] | None:
    """Exponential search for a passing value beyond ``original``.

    Returns ``(failing, passing)`` where ``failing`` still fails and ``passing``
    does not, or ``None`` when the search hits the dtype bound or the budget.
    """
    failing = original
    distance = max(abs(original), 1)
    while True:
        candidate = _step(failing, distance, direction, bounds)
        if candidate == failing:
            return None
        outcome = tracker.holds_on(_with_cell(frame, column, row, candidate, dtype))
        if outcome is None:
            return None
        if not outcome:
            return failing, candidate
        failing = candidate
        distance = distance * 2


def _bisect(
    frame: pl.DataFrame,
    tracker: _Tracker,
    *,
    column: str,
    row: int,
    failing: float,
    passing: float,
    bounds: tuple[int, int] | None,
    dtype: pl.DataType,
) -> tuple[int | float, bool]:
    """Close the bracket onto the failing value adjacent to passing."""
    low, high = failing, passing
    while not _adjacent(low, high, bounds):
        midpoint = _mid(low, high, bounds)
        outcome = tracker.holds_on(_with_cell(frame, column, row, midpoint, dtype))
        if outcome is None:
            return low, False
        if outcome:
            low = midpoint
        else:
            high = midpoint
    return low, True


def _step(
    value: float,
    distance: float,
    direction: Direction,
    bounds: tuple[int, int] | None,
) -> int | float:
    sign = _sign(direction)
    if bounds is not None:
        low, high = bounds
        return min(max(value + sign * distance, low), high)
    candidate = value + sign * distance
    if candidate == value:
        candidate = math.nextafter(value, math.inf if sign > 0 else -math.inf)
    if not math.isfinite(candidate):
        candidate = math.copysign(_FLOAT_LIMIT, sign)
    return candidate


def _sign(direction: Direction) -> int:
    return 1 if direction == "increase" else -1


def _mid(
    low: float,
    high: float,
    bounds: tuple[int, int] | None,
) -> int | float:
    if bounds is not None:
        return (low + high) // 2
    midpoint = low + (high - low) / 2
    if midpoint in (low, high) or not math.isfinite(midpoint):
        midpoint = math.nextafter(low, high)
    return midpoint


def _adjacent(low: float, high: float, bounds: tuple[int, int] | None) -> bool:
    if bounds is not None:
        return abs(high - low) <= 1
    return math.nextafter(low, high) == high


def _bounds(dtype: pl.DataType) -> tuple[int, int] | None:
    """Integer bounds for an integer dtype, ``None`` for an unbounded Float64."""
    name = str(dtype.base_type())
    entry = _INT_BITS.get(name)
    if entry is not None:
        bits, is_signed = entry
        if is_signed:
            limit = 1 << (bits - 1)
            return -limit, limit - 1
        return 0, (1 << bits) - 1
    if name == "Float64":
        return None
    msg = f"minimize_values supports integer and Float64 columns, not {name!r}"
    raise TypeError(msg)


def _with_cell(
    frame: pl.DataFrame, column: str, row: int, value: Any, dtype: pl.DataType
) -> pl.DataFrame:
    values = frame[column].to_list()
    values[row] = value
    return frame.with_columns(pl.Series(column, values, dtype=dtype))


def _rows_still_minimal(frame: pl.DataFrame, tracker: _Tracker) -> bool:
    """Re-check that dropping any single row still passes (monotone value moves kept it)."""
    for row in range(frame.height):
        without = frame[[other for other in range(frame.height) if other != row]]
        outcome = tracker.holds_on(without)
        if outcome is None or outcome:
            return False
    return True


class _Tracker:
    """Budgeted ``fails`` evaluator with a three-state outcome.

    ``holds_on`` returns ``True`` (still fails), ``False`` (passes), or ``None``
    when the budget is spent.  The search treats ``None`` as "unknown" and stops
    rather than reading it as either side of the boundary.
    """

    def __init__(self, fails: FailPredicate, max_evals: int) -> None:
        self._fails = fails
        self.max_evals = max_evals
        self.calls = 0

    def holds_on(self, frame: pl.DataFrame) -> bool | None:
        if self.calls >= self.max_evals:
            return None
        self.calls += 1
        result = self._fails(frame)
        if result is None:
            msg = "fails returned None; the contract requires a bool"
            raise TypeError(msg)
        return bool(result)


__all__ = ["Direction", "ValueReduction", "direction_for_rule", "minimize_values"]
