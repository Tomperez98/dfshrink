"""Render a repro as pasteable code, a markdown table, or a failure line.

:meth:`pycheck.Repro.to_code` and :meth:`pycheck.Repro.to_markdown` are the
public entry points; this module holds the formatting so :mod:`pycheck.shrink`
stays about the algorithm.  :func:`render_diagnosis_markdown` folds the
:class:`~pycheck.Failure` into the same report, so a ticket reads *why* a frame
failed and shows the row that does it.

Rendering is **lossless or loud**: :func:`render_code` rebuilds the frame from
the data and schema it is about to print and panics when the rebuild does not
equal the original.  A dtype whose values cannot be written as Python literals
(a column of :class:`polars.Object`, say) raises instead of emitting code that
would silently build a different frame.
"""

from __future__ import annotations

import datetime
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pycheck.failure import Diagnosis, Failure


def render_code(frame: pl.DataFrame) -> str:
    """Return a pasteable ``pl.DataFrame(...)`` constructor for ``frame``.

    Postcondition: ``eval(render_code(frame))`` -- with only ``polars as pl`` in
    scope -- is a :class:`polars.DataFrame` equal to ``frame``.  A dtype that
    cannot be rendered without loss raises ``TypeError`` rather than emitting
    code that builds a different frame.
    """
    data: dict[str, list[Any]] = {}
    dtypes: dict[str, pl.DataType] = {}
    values: list[str] = []
    schema: list[str] = []
    for name, series in zip(frame.columns, frame.iter_columns(), strict=True):
        ready = _ready_values(series)
        try:
            rendered = _render_values(ready)
        except TypeError as exc:
            msg = f"cannot render column {name!r} as code: {exc}"
            raise TypeError(msg) from exc
        data[name] = ready
        dtypes[name] = series.dtype
        values.append(f"{name!r}: {rendered}")
        schema.append(f"{name!r}: {_render_dtype(series.dtype)}")

    _verify_round_trip(frame, data, dtypes)
    return f"pl.DataFrame(\n    {{{', '.join(values)}}},\n    schema={{{', '.join(schema)}}},\n)"


def render_markdown(frame: pl.DataFrame) -> str:
    """Return ``frame`` as a GitHub-flavoured markdown table.

    Each header carries the column's dtype (``amount (Int64)``), so the table
    documents the schema as well as the values.
    """
    headers = [f"{name} ({dtype})" for name, dtype in frame.schema.items()]
    lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join('---' for _ in headers)} |",
        *(f"| {' | '.join(_render_cell(value) for value in row)} |" for row in frame.iter_rows()),
    ]
    return "\n".join(lines)


def describe_failure(failure: Failure | None) -> str:
    """A short phrase naming the failing rule and column, for a summary line."""
    if failure is None:
        return "no failure metadata"
    rule, column = failure.rule, failure.column
    if column is not None and rule is not None:
        return f"column {column!r} fails rule {rule!r}"
    if column is not None:
        return f"column {column!r} fails"
    if rule is not None:
        return f"rule {rule!r} fails"
    return "validation failed"


def render_diagnosis_markdown(diagnosis: Diagnosis) -> str:
    """A ticket-ready report: why the frame failed, then the minimal repro."""
    failure = diagnosis.failure
    lines = [f"Validation failed: {describe_failure(failure)}."]
    if failure is not None and failure.message:
        lines += ["", *(f"> {line}" for line in failure.message.splitlines())]
    lines += ["", "Minimal repro:", "", render_markdown(diagnosis.repro.frame)]
    return "\n".join(lines)


def _ready_values(series: pl.Series) -> list[Any]:
    """The series' values, as the literals :func:`pl.DataFrame` rebuilds from.

    This is the same data the emitted code carries, so the round-trip check in
    :func:`_verify_round_trip` exercises exactly what ``to_code`` prints.
    Datetime and Duration columns become integer counts in the dtype's own
    unit, which is exact at every unit -- Python datetimes only carry
    microseconds, so a nanosecond column would otherwise lose precision.
    """
    if isinstance(series.dtype, (pl.Datetime, pl.Duration)):
        return series.cast(pl.Int64).to_list()
    return [_to_literal(value, series.dtype) for value in series.to_list()]


def _to_literal(value: Any, dtype: Any) -> Any:
    """Rewrite one value into the literal form ``dtype`` rebuilds it from."""
    if value is None:
        return None
    if isinstance(dtype, (pl.List, pl.Array)):
        return [_to_literal(item, dtype.inner) for item in value]
    if isinstance(dtype, pl.Struct):
        fields = {field.name: field.dtype for field in dtype.fields}
        return {key: _to_literal(item, fields.get(key)) for key, item in value.items()}
    if isinstance(dtype, (pl.Date, pl.Time)) or isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(dtype, pl.Decimal) or isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime.timedelta):
        return value / datetime.timedelta(microseconds=1)
    return value


def _render_values(values: Sequence[Any]) -> str:
    return f"[{', '.join(_render_value(value) for value in values)}]"


def _render_value(value: Any) -> str:
    """A Python literal for a value already reduced by :func:`_to_literal`."""
    if value is None or isinstance(value, (bool, int, str, bytes)):
        return repr(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "float('nan')"
        if math.isinf(value):
            return "float('inf')" if value > 0 else "float('-inf')"
        return repr(value)
    if isinstance(value, (list, tuple)):
        return f"[{', '.join(_render_value(item) for item in value)}]"
    if isinstance(value, dict):
        items = ", ".join(f"{_render_value(k)}: {_render_value(v)}" for k, v in value.items())
        return f"{{{items}}}"
    msg = f"cannot render value of type {type(value).__name__!r} as code"
    raise TypeError(msg)


def _render_dtype(dtype: Any) -> str:
    """A ``pl.<Dtype>(...)`` expression that reconstructs ``dtype`` exactly."""
    if isinstance(dtype, pl.List):
        return f"pl.List({_render_dtype(dtype.inner)})"
    if isinstance(dtype, pl.Array):
        return f"pl.Array({_render_dtype(dtype.inner)}, {dtype.size})"
    if isinstance(dtype, pl.Struct):
        fields = ", ".join(
            f"{field.name!r}: {_render_dtype(field.dtype)}" for field in dtype.fields
        )
        return f"pl.Struct({{{fields}}})"
    if isinstance(dtype, pl.Datetime):
        if dtype.time_zone is None:
            return f"pl.Datetime(time_unit={dtype.time_unit!r})"
        return f"pl.Datetime(time_unit={dtype.time_unit!r}, time_zone={dtype.time_zone!r})"
    if isinstance(dtype, pl.Duration):
        return f"pl.Duration(time_unit={dtype.time_unit!r})"
    if isinstance(dtype, pl.Decimal):
        return f"pl.Decimal(precision={dtype.precision}, scale={dtype.scale})"
    if isinstance(dtype, pl.Enum):
        return f"pl.Enum({dtype.categories.to_list()!r})"
    return f"pl.{dtype.base_type()}"


def _render_cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return _render_value(value)
    text = value if isinstance(value, str) else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _verify_round_trip(
    frame: pl.DataFrame,
    data: dict[str, list[Any]],
    dtypes: dict[str, pl.DataType],
) -> None:
    """Postcondition check: the data and schema we print rebuild ``frame``."""
    msg = f"to_code cannot render this frame without loss; columns: {dict(frame.schema)}"
    try:
        rebuilt = pl.DataFrame(data, schema=dtypes)
    except Exception as exc:  # one vocabulary for any rebuild failure
        raise TypeError(msg) from exc
    if not rebuilt.equals(frame):
        raise TypeError(msg)
