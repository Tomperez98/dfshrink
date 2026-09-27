"""Tests for repro rendering: ``to_code``, ``to_markdown``, and summaries.

Phase 1 makes a minimal repro *usable*: a pasteable constructor, a markdown
table for a ticket, and a one-line summary.  Rendering is lossless or loud, so
the contract tests below pin both the round-trip and the panic on an
unrenderable dtype.
"""

from __future__ import annotations

import datetime

import polars as pl
import pytest

from dfshrink import Diagnosis, Failure, Repro, shrink_rows
from dfshrink._render import describe_failure


def repro(frame: pl.DataFrame) -> Repro:
    """Wrap ``frame`` as a :class:`Repro`.  Crashes the test on misuse."""
    return Repro(
        frame=frame,
        original_rows=frame.height,
        predicate_calls=0,
        minimality_proven=True,
    )


def round_trip(code: str) -> pl.DataFrame:
    """Evaluate generated code the way a reader would: only ``pl`` in scope."""
    result: object = eval(code, {"pl": pl})  # noqa: S307
    assert isinstance(result, pl.DataFrame)
    return result


DFRAMES = [
    pl.DataFrame({"x": [1, -2], "y": [1.5, 2.0]}),
    pl.DataFrame({"s": ["a", None], "b": [True, False]}),
    pl.DataFrame({"n": [None, None]}, schema={"n": pl.Null}),
    pl.DataFrame({"i32": [1, 2]}, schema={"i32": pl.Int32}),
    pl.DataFrame({"d": [datetime.date(2020, 1, 1), None]}, schema={"d": pl.Date}),
    pl.DataFrame({"t": ["2020-01-01T12:00:00.123456", None]}, schema={"t": pl.Datetime("us")}),
    pl.DataFrame({"t": [1_500_000_000_000_000_001, None]}, schema={"t": pl.Datetime("ns")}),
    pl.DataFrame({"tz": [1_577_880_000_000_000]}, schema={"tz": pl.Datetime("us", "UTC")}),
    pl.DataFrame({"time": [datetime.time(12, 30, 0), None]}, schema={"time": pl.Time}),
    pl.DataFrame({"dur": [1000, None]}, schema={"dur": pl.Duration("us")}),
    pl.DataFrame({"dec": ["1.23", None]}, schema={"dec": pl.Decimal(38, 2)}),
    pl.DataFrame({"bin": [b"\x00\x01", None]}, schema={"bin": pl.Binary}),
    pl.DataFrame({"l": [[1, 2], [3]]}, schema={"l": pl.List(pl.Int64)}),
    pl.DataFrame({"a": [[1, 2, 3]]}, schema={"a": pl.Array(pl.Int64, 3)}),
    pl.DataFrame({"st": [{"a": 1}]}, schema={"st": pl.Struct({"a": pl.Int64})}),
    pl.DataFrame({"e": ["a", "b"]}, schema={"e": pl.Enum(["a", "b"])}),
    pl.DataFrame({"c": ["a", "b"]}, schema={"c": pl.Categorical}),
    pl.DataFrame({"f": [float("nan"), float("inf"), float("-inf")]}),
]


# --- to_code -----------------------------------------------------------------


@pytest.mark.parametrize("frame", DFRAMES)
def test_to_code_round_trips(frame: pl.DataFrame) -> None:
    rebuilt = round_trip(repro(frame).to_code())

    assert rebuilt.equals(frame)


def test_to_code_round_trips_a_real_shrink_result() -> None:
    df = pl.DataFrame({"id": [0, 1, 2], "amount": [10, -9, 20], "tag": ["a", "b", "c"]})

    found = shrink_rows(df, lambda d: bool((d["amount"] < 0).any()))

    assert found is not None
    assert round_trip(found.to_code()).equals(found.frame)


def test_to_code_rejects_unrenderable_dtype() -> None:
    frame = pl.DataFrame({"o": [object()]}, schema={"o": pl.Object})

    with pytest.raises(TypeError, match="column 'o'"):
        repro(frame).to_code()


def test_to_code_rejects_a_lossy_nested_temporal() -> None:
    # List(Datetime("ns")) loses precision through Python datetimes, so the
    # postcondition check must refuse it rather than print lossy code.
    frame = pl.DataFrame(
        {"d": [[1_500_000_000_000_000_001]]},
        schema={"d": pl.List(pl.Datetime("ns"))},
    )

    with pytest.raises(TypeError, match="without loss"):
        repro(frame).to_code()


def test_to_code_rejects_an_unrebuildable_nested_dtype() -> None:
    # A nested Duration renders as float literals that polars cannot read back;
    # the rebuild failure is reported as the same "without loss" TypeError.
    frame = pl.DataFrame(
        {"d": [[1000, 2000]]},
        schema={"d": pl.List(pl.Duration("us"))},
    )

    with pytest.raises(TypeError, match="without loss"):
        repro(frame).to_code()


# --- to_markdown -------------------------------------------------------------


def test_to_markdown_names_dtypes_and_values() -> None:
    df = pl.DataFrame(
        {"id": [2], "amount": [510], "currency": [None]},
        schema={"id": pl.Int64, "amount": pl.Int64, "currency": pl.String},
    )

    markdown = repro(df).to_markdown()

    lines = markdown.splitlines()
    assert lines[0] == "| id (Int64) | amount (Int64) | currency (String) |"
    assert lines[1] == "| --- | --- | --- |"
    assert lines[2] == "| 2 | 510 | null |"


def test_to_markdown_escapes_pipes() -> None:
    df = pl.DataFrame({"s": ["a|b"]})

    assert r"a\|b" in repro(df).to_markdown()


def test_to_markdown_renders_non_finite_floats() -> None:
    df = pl.DataFrame({"x": [float("nan"), float("inf")]})

    markdown = repro(df).to_markdown()

    assert "float('nan')" in markdown
    assert "float('inf')" in markdown


# --- failure descriptions ----------------------------------------------------


def test_describe_failure_covers_each_field_shape() -> None:
    fieldless = Failure(rule=None, column=None, message=None, invalid_rows=None)

    assert describe_failure(None) == "no failure metadata"
    assert describe_failure(
        Failure(rule="min", column="amount", message=None, invalid_rows=None)
    ) == ("column 'amount' fails rule 'min'")
    assert describe_failure(
        Failure(rule=None, column="amount", message=None, invalid_rows=None)
    ) == ("column 'amount' fails")
    assert describe_failure(Failure(rule="min", column=None, message=None, invalid_rows=None)) == (
        "rule 'min' fails"
    )
    assert describe_failure(fieldless) == "validation failed"


def test_diagnosis_markdown_quotes_the_validator_message() -> None:
    found = Diagnosis(
        repro=repro(pl.DataFrame({"amount": [-9]})),
        failure=Failure(
            rule="min",
            column="amount",
            message="line one\nline two",
            invalid_rows=None,
        ),
    )

    markdown = found.to_markdown()

    assert "> line one" in markdown
    assert "> line two" in markdown


# --- summary and replay ------------------------------------------------------


def test_summary_reports_the_shape_of_the_result() -> None:
    df = pl.DataFrame({"x": [-5, 3, -1, 7, 2]})

    found = shrink_rows(df, lambda d: bool(d["x"].sum() > 0))

    assert found is not None
    assert "predicate calls" in str(found)
    assert "removed 4 of 5" in str(found)
    assert repr(found).startswith("Repro(rows=1, removed_rows=4,")


def test_as_frame_is_the_replayable_repro() -> None:
    df = pl.DataFrame({"x": [1, -2, 3]})

    found = shrink_rows(df, lambda d: bool((d["x"] < 0).any()))

    assert found is not None
    assert found.as_frame().equals(found.frame)
