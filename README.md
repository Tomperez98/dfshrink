# pycheck

**Shrink a failing DataFrame to the fewest rows that still break.**

A validator tells you *that* a 2-million-row frame broke a rule — not *which*
rows. `shrink_rows` runs that same validator over smaller and smaller subsets
and returns the minimal frame that still fails:

```python
import polars as pl
from pycheck import shrink_rows

df = pl.DataFrame(
    {
        "id": [0, 1, 2, 3, 4, 5],
        "amount": [10, 20, 510, 30, 40, 50],
        "currency": ["EUR", "EUR", None, "EUR", "EUR", "EUR"],
    }
)


def bug(df: pl.DataFrame) -> bool:
    return bool(((df["amount"] > 500) & (df["currency"].is_null())).any())


repro = shrink_rows(df, bug)
print(repro.frame)
```

```
shape: (1, 3)
┌─────┬────────┬──────────┐
│ id  ┆ amount ┆ currency │
│ --- ┆ ---    ┆ ---      │
│ i64 ┆ i64    ┆ str      │
╞═════╪════════╪══════════╡
│ 2   ┆ 510    ┆ null     │
└─────┴────────┴──────────┘
```

Six rows in, one row out — small enough to paste into a ticket or a test.

## Install

Not on PyPI yet — install from a checkout:

```bash
uv sync            # or: pip install -e .
```

Requires Python 3.14+ and Polars.

## What it does

`shrink_rows(frame, fails)` runs delta debugging (`ddmin`) over a Polars frame's
rows and returns the smallest subset on which `fails` is still `True`. It's a
minimal bug repro for data — the Python/Polars equivalent of R's
`minex::reduce_rows`.

**Why not just `.filter()`?** Filtering needs a per-row mask: you have to write
the failing rule as an expression. Shrinking only needs the black-box predicate
you already have — the `df -> bool` that told you the frame failed. When the
failure is an aggregate, a cross-row interaction, or a validator that returns
only "failed", there is no mask to filter on; there is only "does this subset
still fail?". That's the question shrinking answers. If you *can* write the
mask, `filter` is simpler — use it. This is for when you can't.

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

`fails` is the seam — a lambda, a test assertion, or the adapter from
`pycheck.ext.dataframely` / `pycheck.ext.pandera` / `pycheck.ext.patito` (next
section). Keep it pure:
shrinking re-runs it many times, so it must be deterministic.

## Shrink a dataframely, pandera, or patito schema

A schema tells you *that* a rule broke — not which rows did it:

```text
dataframely.exc.ValidationError: 1 rules failed validation:
 * Column 'amount' failed validation for 1 rules:
   - 'min' failed for 1 rows
```

Hand the schema to `shrink_rows` instead, and it returns the row that did it:

```text
dataframely: [-9]
```

Same rule, same frame — one row out. You already wrote the validator, so there's
nothing to re-express: pass the schema itself. `shrink_rows` minimizes over a
plain `DataFrame -> bool` predicate; to shrink against a validation library,
import the adapter that owns that library — the base `pycheck` package never
imports it, so the dependency stays optional.

```python
import dataframely as dy
from pycheck.ext.dataframely import shrink_rows


class HouseSchema(dy.Schema):
    amount = dy.Int64(nullable=False, min=0)


repro = shrink_rows(df, HouseSchema)  # inverts HouseSchema.is_valid(df)
```

```python
import pandera.polars as pa
from pycheck.ext.pandera import shrink_rows


class Accounts(pa.DataFrameModel):
    amount: pa.typing.Series[int] = pa.Field(gt=0)


repro = shrink_rows(df, Accounts)  # wraps Accounts.validate(df)
```

```python
import patito as pt
from pycheck.ext.patito import shrink_rows


class House(pt.Model):
    amount: int = pt.Field(ge=0)


repro = shrink_rows(df, House)  # wraps House.validate(df)
```

`pycheck.ext.dataframely` adapts `is_valid(df) -> bool`; `pycheck.ext.pandera`
and `pycheck.ext.patito` adapt `validate(df)`-raises; each also exposes
`as_predicate` for the raw predicate. Install the library you need with
`uv sync --extra dataframely`, `--extra pandera`, or `--extra patito`. Runnable
versions live in
[`examples/dataframely_schema.py`](examples/dataframely_schema.py),
[`examples/pandera_schema.py`](examples/pandera_schema.py), and
[`examples/patito_schema.py`](examples/patito_schema.py); the dependency-free
seam is [`examples/predicate.py`](examples/predicate.py). The frame must already
match the schema's columns and dtypes — shrinking only removes rows, so a
structural mismatch is the caller's bug.

## Fast: ~log₂(n) predicate calls

The only cost that scales with your data is your predicate. `ddmin` narrows by
chunks instead of removing one row at a time — which is `O(n²)` calls — so a bad
row is isolated in ~log₂(n) calls:

| Frame | Bad rows | Result | Predicate calls |
|---|---|---|---|
| 20,000 rows | 1 | 1 row | 16–29 |
| 6 rows | 1 | 1 row | 4 |

The call count depends on where the bad rows sit; the range is measured. With a
cheap predicate the shrinking itself adds ~1 ms of overhead — if your predicate
is expensive, cap it with `max_evals`.

That ~log₂(n) figure is the common case: a few bad rows among many. The opposite
case is when the failure needs *most* of the frame — a sum over nearly every
row, say. Then every proper subset passes, `ddmin` has nothing to remove, and
the budget (`max_evals`, default 10,000) is what stops the search. The result is
still a valid repro — the frame itself, with `minimality_proven=False` — because
no smaller subset reproduces the failure. Shrinking cannot reduce what no
smaller subset reproduces.

## When not to use it

- **Not a validator.** It doesn't define or check rules; it runs *after* one
  fails, using your predicate as the oracle.
- **Rows, not values.** It drops rows; it doesn't minimize a cell to a boundary
  value, and column reduction isn't built.
- **No pipeline attribution.** It won't tell you *which step* (a join, a cast)
  introduced the bad rows.
- **Needs a pure, deterministic predicate.** Nondeterminism makes shrinking
  meaningless.

## The contract

`shrink_rows(frame, fails, *, max_evals=10_000) -> Repro | None`

- **Bugs panic.** An empty frame or `max_evals < 1` raises `ValueError`; a
  `fails` that raises propagates unchanged (never swallowed as "does not
  fail"); a `fails` that returns `None` raises `TypeError`.
- **Expected failures are values.** A non-failing input returns `None`; an
  exhausted budget returns a `Repro` with `minimality_proven=False` — still a
  valid repro, just not proven minimal.
- **On success.** `Repro.frame` fails, has ≥1 row, preserves the original row
  order, and when `minimality_proven` is `True`, removing any single row makes
  `fails` return `False`.

Full contract, algorithm, and references: [`src/pycheck/shrink.py`](src/pycheck/shrink.py).

## Development

```bash
uv run pytest
uv run ty check   # strict: every diagnostic is an error
```
