# dfshrink

**Your data contract failed. Get the smallest frame that still breaks it — and a regression test.**

A validator tells you the frame is bad; it can't tell you *which* rows. `shrink_rows`
runs that same predicate over smaller and smaller subsets and returns the minimal
frame that still fails:

```python
import polars as pl
from dfshrink import shrink_rows

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
only question, and shrinking answers it. Paste the row into a regression test with
`repro.to_code()`, or drop `repro.to_markdown()` into the incident ticket.

That's the data engineer's loop: **a contract check fails → the smallest still-bad
frame and the broken rule → a committed test and a fix** — without hand-slicing a
warehouse extract.

## What it is

dfshrink is the triage step between "the contract check failed" and "here is the
fix." Point it at the validator you already run — dataframely, pandera, patito, or
a plain `DataFrame -> bool` — and it returns the smallest frame that still fails,
plus the rule and column that broke.

`shrink_rows(frame, fails, *, max_evals=10_000) -> Repro | None` runs delta
debugging (`ddmin`) over a Polars frame's rows and returns the smallest subset on
which `fails` is still `True` — a minimal repro for a data bug, the Python/Polars
analog of R's `minex::reduce_rows`.

## Install

Not on PyPI yet — install from a checkout:

```bash
uv sync            # or: pip install -e .
```

Requires Python 3.12+ and Polars. The base package imports only Polars; each
validator adapter is an extra (`uv sync --extra dataframely`, `--extra pandera`,
`--extra patito`).

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
from dfshrink.ext.dataframely import shrink_rows


class HouseSchema(dy.Schema):
    amount = dy.Int64(nullable=False, min=0)


repro = shrink_rows(df, HouseSchema)  # inverts HouseSchema.is_valid(df)
```

Same shape for the others — `dfshrink.ext.pandera` wraps `validate(df)`-raises,
`dfshrink.ext.patito` wraps `Model.validate(df)`:

```python
import pandera.polars as pa
from dfshrink.ext.pandera import shrink_rows

schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
repro = shrink_rows(df, schema)
```

```python
import patito as pt
from dfshrink.ext.patito import shrink_rows


class House(pt.Model):
    amount: int = pt.Field(ge=0)


repro = shrink_rows(df, House)
```

Each module also exposes `as_predicate` for the raw `DataFrame -> bool`. The
frame must already match the schema's columns and dtypes — shrinking only removes
rows, so a structural mismatch is the caller's bug. Runnable versions:
[`examples/dataframely_schema.py`](https://github.com/Tomperez98/pycheck/blob/main/examples/dataframely_schema.py),
[`examples/pandera_schema.py`](https://github.com/Tomperez98/pycheck/blob/main/examples/pandera_schema.py),
[`examples/patito_schema.py`](https://github.com/Tomperez98/pycheck/blob/main/examples/patito_schema.py), and the
dependency-free [`examples/predicate.py`](https://github.com/Tomperez98/pycheck/blob/main/examples/predicate.py).

## Fast: ~log₂(n) predicate calls

The only cost that scales with your data is your predicate. `ddmin` narrows by
chunks instead of removing one row at a time (which is `O(n²)` calls), so a bad
row is isolated in ~log₂(n) calls:

| Frame | Bad rows | Result | Predicate calls |
|---|---|---|---|
| 20,000 rows | 1 | 1 row | 16–29 |
| 6 rows | 1 | 1 row | 4 |

Call counts depend on where the bad rows sit; the range is measured. Candidates
are selected with `DataFrame.slice`, so copying the frame is not the cost: with a
cheap predicate, 20,000 rows shrink to one in ~0.25 ms. Cap the predicate calls
with `max_evals` (default 10,000) —
[performance in depth →](https://github.com/Tomperez98/pycheck/blob/main/docs/performance.md).

## Who it's for — and when not to use it

**It's for data engineers running Polars pipelines with a pass/fail validator** —
a data contract, a schema check, or a cross-row invariant (totals, uniqueness,
ordering) you assert in a test, in CI, or during an incident. The payoff is
turning a failed check into the one row and rule to fix, a regression test to
commit, and a ticket the upstream owner can act on.

It is deliberately narrow:

- **Polars only.** pandas and SQL/warehouse data aren't supported today. If the
  bad data lives in a warehouse, materialize the frame first.
- **Not a validator.** It doesn't define or check rules; it runs *after* one
  fails, using your predicate as the oracle.
- **Not production monitoring.** It's a developer/CI debugging tool, not a
  data-observability service.
- **No pipeline attribution.** It won't tell you *which step* (a join, a cast)
  introduced the bad rows — only which rows.
- **Columns are schema-aware.** It minimizes rows and numeric values; dropping
  columns needs the adapter's explainer (`diagnose(..., columns=True)`), because a
  black-box predicate cannot tell a real failure from a frame that went
  structurally invalid.
- **Needs a pure, deterministic predicate.** Nondeterminism makes shrinking
  meaningless.

## Learn more

The README is the front door; each guide owns one task in depth:

- **[Diagnose the failure](https://github.com/Tomperez98/pycheck/blob/main/docs/diagnose.md)** — get the rule and column the validator flagged, not just the rows.
- **[Fail with a repro in CI](https://github.com/Tomperez98/pycheck/blob/main/docs/ci.md)** — `assert_valid` turns a failed job into a minimal repro.
- **[Move the value to the boundary](https://github.com/Tomperez98/pycheck/blob/main/docs/minimize-values.md)** — shrink a bad cell to the last value that still fails.
- **[Drop the columns the rule does not need](https://github.com/Tomperez98/pycheck/blob/main/docs/minimize-columns.md)** — schema-aware column reduction.
- **[Performance in depth](https://github.com/Tomperez98/pycheck/blob/main/docs/performance.md)** — call counts, the worst case, and `max_evals`.
- **[The contract](https://github.com/Tomperez98/pycheck/blob/main/docs/contract.md)** — panic/value semantics, minimality guarantees, and the algorithm.

## Development

[mise](https://mise.jdx.dev/) drives every task, so a laptop and CI run the same
commands:

```bash
mise install       # pinned Python and uv
mise run setup     # every dependency, including the validator extras
mise run ci        # the merge gate: format, lint, type, hygiene, tests, examples, build, smoke
```

While iterating, run one tier: `mise run test`, `mise run lint`, `mise run
type`. Every diagnostic is an error. See [CONTRIBUTING.md](CONTRIBUTING.md) for
the pull-request checklist, and [RELEASING.md](RELEASING.md) for how a release
is cut.
