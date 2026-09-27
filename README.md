# pycheck

**Shrink a failing DataFrame to the fewest rows that still break.**

Your validator says the frame is bad. It doesn't say *which* rows. `shrink_rows`
runs that same predicate over smaller and smaller subsets and returns the
minimal frame that still fails:

```python
import polars as pl
from pycheck import shrink_rows

df = pl.DataFrame(
    {
        "order_id": [1, 1, 1, 2, 2, 3],
        "amount": [10, 20, 30, 5, 7, 9],
        "total": [50, 50, 50, 12, 12, 9],
    }
)


def bug(df: pl.DataFrame) -> bool:
    """Each order's line items must sum to its declared total."""
    bad = (
        df.group_by("order_id")
        .agg(pl.col("amount").sum().alias("lines"), pl.col("total").first())
        .filter(pl.col("lines") != pl.col("total"))
    )
    return bad.height > 0


repro = shrink_rows(df, bug)
print(repro)
print(repro.frame)
```

```
Repro(1 row, removed 5 of 6, 4 predicate calls, minimality proven)
shape: (1, 3)
┌──────────┬────────┬───────┐
│ order_id ┆ amount ┆ total │
│ ---      ┆ ---    ┆ ---   │
│ i64      ┆ i64    ┆ i64   │
╞══════════╪════════╪═══════╡
│ 1        ┆ 10     ┆ 50    │
└──────────┴────────┴───────┘
```

Six rows in, one row out — in four calls to `bug`. The rule is an aggregate, so
there is no per-row mask to `.filter()` on; "does this subset still fail?" is the
only question, and shrinking answers it.

## Install

Not on PyPI yet — install from a checkout:

```bash
uv sync            # or: pip install -e .
```

Requires Python 3.12+ and Polars. The base package imports only Polars; each
validator adapter is an extra (`uv sync --extra dataframely`, `--extra pandera`,
`--extra patito`).

## What it is

`shrink_rows(frame, fails, *, max_evals=10_000) -> Repro | None` runs delta
debugging (`ddmin`) over a Polars frame's rows and returns the smallest subset on
which `fails` is still `True` — a minimal bug repro for data, the Python/Polars
analog of R's `minex::reduce_rows`.

**If you can write the failing rule as a per-row mask, use `.filter()` — it's
simpler.** Shrinking is for when you can't: a validator that returns a single bit
(`is_valid`, `validate`, patito), an aggregate, or a cross-row interaction. There
is no mask then; there is only "does this subset still fail?".

## Reading the result

```python
repro = shrink_rows(df, bug)

if repro is None:
    print("the frame does not fail")  # expected failure -> None
else:
    print(repro.frame)  # the minimal failing rows
    print(repro.removed_rows)  # rows dropped from the input
    print(repro.minimality_proven)  # True => removing any one row makes it pass
```

`fails` is the seam — a lambda, a test assertion, or a schema adapter (next
section). Keep it pure: shrinking re-runs it many times, so it must be
deterministic.

### Paste it into a test or a ticket

A `Repro` renders itself for wherever the repro is going:

```python
repro.to_code()  # a pl.DataFrame({...}, schema={...}) constructor
repro.to_markdown()  # a markdown table, dtypes in the headers
str(repro)  # 'Repro(1 row, removed 5 of 6, 4 predicate calls, minimality proven)'
repro.as_frame()  # the replayed frame, to re-run your predicate on
```

`to_code()` round-trips: `eval(repro.to_code())`, with only `polars as pl` in
scope, rebuilds an equal frame — so the constructor goes straight into a test.
A dtype that cannot be rendered without loss (a column of `pl.Object`, say)
raises `TypeError` rather than emitting code that quietly builds a different
frame.

## Shrink against dataframely, pandera, or patito

A schema tells you *that* a rule broke — not which rows did it:

```text
dataframely.exc.ValidationError: 1 rules failed validation:
 * Column 'amount' failed validation for 1 rules:
   - 'min' failed for 1 rows
```

Hand the schema to `shrink_rows` instead, and it returns the row that did it.
You already wrote the validator, so there's nothing to re-express:

```python
import dataframely as dy
from pycheck.ext.dataframely import shrink_rows


class HouseSchema(dy.Schema):
    amount = dy.Int64(nullable=False, min=0)


repro = shrink_rows(df, HouseSchema)  # inverts HouseSchema.is_valid(df)
```

Same shape for the others — `pycheck.ext.pandera` wraps `validate(df)`-raises,
`pycheck.ext.patito` wraps `Model.validate(df)`:

```python
import pandera.polars as pa
from pycheck.ext.pandera import shrink_rows

schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
repro = shrink_rows(df, schema)
```

```python
import patito as pt
from pycheck.ext.patito import shrink_rows


class House(pt.Model):
    amount: int = pt.Field(ge=0)


repro = shrink_rows(df, House)
```

Each module also exposes `as_predicate` for the raw `DataFrame -> bool`. The
frame must already match the schema's columns and dtypes — shrinking only removes
rows, so a structural mismatch is the caller's bug. Runnable versions:
[`examples/dataframely_schema.py`](examples/dataframely_schema.py),
[`examples/pandera_schema.py`](examples/pandera_schema.py),
[`examples/patito_schema.py`](examples/patito_schema.py), and the
dependency-free [`examples/predicate.py`](examples/predicate.py).

## Get the reason, not just the rows: `diagnose`

`shrink_rows` answers *which rows*. `diagnose` also answers *why* — the rule and
column the validator flagged — as a ticket-ready report:

```python
from pycheck.ext.dataframely import diagnose

found = diagnose(df, HouseSchema)
print(found.to_markdown())
```

```text
Validation failed: column 'amount' fails rule 'amount|min'.

Minimal repro:

| amount (Int64) |
| --- |
| -9 |
```

`diagnose` returns `None` when the frame passes, else a `pycheck.Diagnosis`
whose `repro` is the same minimal repro `shrink_rows` would produce, and whose
`failure` carries the rule, column, and (when the validator exposes them) the
invalid rows. When the validator reports the invalid rows (dataframely, pandera),
shrinking starts there instead of over the whole frame; when it doesn't (patito),
`diagnose` falls back to black-box shrinking and still reports the failing
column.

## Move the value to the boundary, not just the row

Shrinking drops rows; it can't say *how far* past the line a cell is. Under a
`min=0` rule the failing row might be `amount=-9`, but the interesting repro is
the last value that still fails:

```python
from pycheck import minimize_values
from pycheck.ext.dataframely import as_predicate, diagnose

found = diagnose(df, HouseSchema)  # repro + why (rule 'amount|min')
reduced = minimize_values(found, as_predicate(HouseSchema))

reduced.repro.frame  # amount == -1 -- the boundary, not -9
reduced.proven  # True: -1 is the failing value next to passing
reduced.column  # 'amount'
reduced.direction  # 'increase'
```

`minimize_values` reads the column from the diagnosis and the direction from the
rule name (`min`/`greater` → increase, `max`/`less` → decrease). Pass a bare
`Repro` with `column=` and `direction=` instead. It assumes the predicate is
monotone *along that column*; when no passing value is found, or the budget runs
out, the cell is left untouched and `proven` is `False` — the step never guesses
a boundary it can't show. Only integer and `Float64` columns are supported.

## Fail a test with the repro, not the traceback

`pycheck.ext.pytest.assert_valid` is the pytest-shaped replacement for
`assert schema.is_valid(df)`. Pass the adapter's `diagnose` and it either returns
silently or fails the test with the rule/column and the minimal repro:

```python
from pycheck.ext.dataframely import diagnose
from pycheck.ext.pytest import assert_valid


def test_house_schema(df):
    assert_valid(df, HouseSchema, diagnose=diagnose)
```

It imports no validator library and touches no global state, so it works the same
inside a fixture.

## Fast: ~log₂(n) predicate calls

The only cost that scales with your data is your predicate. `ddmin` narrows by
chunks instead of removing one row at a time (which is `O(n²)` calls), so a bad
row is isolated in ~log₂(n) calls:

| Frame | Bad rows | Result | Predicate calls |
|---|---|---|---|
| 20,000 rows | 1 | 1 row | 16–29 |
| 6 rows | 1 | 1 row | 4 |

Call counts depend on where the bad rows sit; the range is measured. With a cheap
predicate the shrinking itself adds ~1 ms of overhead — if your predicate is
expensive, cap it with `max_evals` (default 10,000).

That ~log₂(n) figure is the common case: a few bad rows among many. The opposite
case is when the failure needs *most* of the frame — a sum over nearly every row.
Then every proper subset passes, `ddmin` has nothing to remove, and the budget is
what stops the search. The result is still a valid repro (the frame itself, with
`minimality_proven=False`) — no smaller subset reproduces the failure.

## Who it's for — and when not to use it

**It's for Python data pipelines on Polars with a pass/fail validator**: a
transformation, a data contract, or a schema check you run in a test, a CI job,
or locally before shipping. The payoff is turning a failed check into the one row
to look at, paste into a test, or hand to the data owner.

It is deliberately narrow:

- **Polars only.** pandas and SQL/warehouse data aren't supported today. If the
  bad data lives in a warehouse, you must materialize the frame first.
- **Not a validator.** It doesn't define or check rules; it runs *after* one
  fails, using your predicate as the oracle.
- **Not production monitoring.** It's a developer/CI debugging tool, not a
  data-observability service.
- **No pipeline attribution.** It won't tell you *which step* (a join, a cast)
  introduced the bad rows — only which rows.
- **Columns, not yet.** It minimizes rows and numeric values, but doesn't drop
  columns.
- **Needs a pure, deterministic predicate.** Nondeterminism makes shrinking
  meaningless.

## The contract

`shrink_rows(frame, fails, *, max_evals=10_000) -> Repro | None`

- **Bugs panic.** An empty frame or `max_evals < 1` raises `ValueError`; a
  `fails` that raises propagates unchanged (never swallowed as "does not fail");
  a `fails` that returns `None` raises `TypeError`.
- **Expected failures are values.** A non-failing input returns `None`; an
  exhausted budget returns a `Repro` with `minimality_proven=False` — still a
  valid repro, just not proven minimal.
- **On success.** `Repro.frame` fails, has ≥1 row, preserves the original row
  order, and when `minimality_proven` is `True`, removing any single row makes
  `fails` return `False`.

Full contract, algorithm, and references:
[`src/pycheck/shrink.py`](src/pycheck/shrink.py).

## Development

```bash
uv run pytest
uv run ty check   # strict: every diagnostic is an error
```
