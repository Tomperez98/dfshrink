# pycheck roadmap

> How `pycheck` grows from "shrink a failing DataFrame to the fewest rows that
> still break" into a smart, valuable tool — without breaking the contract that
> makes it good.

This roadmap is grounded in the deep-research brief
`outputs/pycheck-feature-roadmap.md` (and the earlier `outputs/dataframe-contract-gaps.md`).
It is a *planning* document: phases are ordered by value-to-risk, each phase has a
concrete shape and acceptance criteria, and the whole thing is held to one rule —
**never regress the fail-fast contract** (bugs panic, expected failures return
values, minimality is reported honestly).

**Status:** Phases 0–1 are shipped (2026-09-27). Phases 2–4 are open.

---

## The thesis, in one sentence

`shrink_rows` currently treats every validator as a black box that returns a
`bool`, then re-discovers *which rows fail* with ~log₂(n) predicate calls. But
the validators we already adapt — dataframely, pandera, patito — *know* why the
frame fails: the rule, the column, and the invalid rows. The roadmap is about
**surfacing that knowledge without giving up the black-box fallback**:

> Given a frame and a validator, return the smallest failing subset **and** the
> rule/column that failed, as a pasteable repro — using the validator's own
> failure metadata when it has any, and falling back to black-box delta
> debugging when it doesn't.

Everything below is a step toward that sentence.

---

## Non-goals (so we don't drift)

- **Not another validator.** We never define or check rules; we run *after* one
  fails. (Established in the prior brief — the validator space is saturated.)
- **Not pipeline attribution (yet).** "Which join/cast introduced these rows"
  is real prior art (OptDebug, BigSift, BugDoc) but it's a *pipeline-graph*
  product with instrumentation and provenance capture — a different, heavier
  tool. Tracked as a deferred north-star, not a phase here.
- **Not a schema/static-typing library.** Column typing is being absorbed by
  Colnade, typedframes, frameright, pandera-mypy.
- **No new hard dependency in `pycheck`.** The base package must keep importing
  only `polars`; every validator stays behind its extra.

---

## Phase 0 — Failure-aware adapters *(the smart-tool core)* ✅ DONE

**Why.** This was the single highest-value change. `pycheck.ext.dataframely`
called `schema.is_valid(df)` and inverted to a `bool`; `pycheck.ext.pandera` and
`pycheck.ext.patito` caught the validation exception and returned `True`. All
three threw away the *reason* the frame failed — dataframely's `FailureInfo`
(`counts()`, `cooccurrence_counts()`, `invalid()`), pandera's
`SchemaErrors.failure_cases` / `.data`, patito's per-column error detail.

**Shipped.**

- Core types in `src/pycheck/failure.py`, exported from `pycheck`:
  `Failure(rule, column, message, invalid_rows)`, `Diagnosis(repro, failure)`,
  and the `Explainer` alias (`DataFrame -> Failure | None`).
- `make_diagnose(as_failure, as_predicate)` in `pycheck/ext/_adapter.py`, plus a
  per-adapter `diagnose(frame, schema, *, max_evals) -> Diagnosis | None`.
- `as_failure(schema)` on each adapter:
  - **dataframely** — `Schema.filter(df)` → `FailureInfo`: `rule` = the
    most-failing rule (`"amount|min"`), `column` derived from the rule key,
    `invalid_rows` = `FailureInfo.invalid()`.
  - **pandera** — `validate(lazy=True)` → `SchemaErrors.failure_cases`: `rule` =
    check name, `column`, `invalid_rows` = the indexed failing rows.
  - **patito** — `DataFrameValidationError.errors()`: `column` + `rule` (error
    type) + message; no row info, so `invalid_rows` is `None`.
- `diagnose` explains first, shrinks second: when `invalid_rows` is present it
  shrinks *within that set* (always via ddmin, so `minimality_proven` stays
  honest); otherwise it falls back to black-box `shrink_rows` over the full frame.

**Contract, as shipped.**

- `shrink_rows(frame, fails)` is untouched — `diagnose(...).repro` equals
  `shrink_rows(...)` for the same schema (pinned by tests).
- Bugs panic: empty frame / `max_evals < 1` → `ValueError`; a validator that
  reports a failure its predicate won't reproduce → assertion.
- Expected failures return values: a passing frame → `None`.
- **Deviation from the original sketch:** a structural mismatch (missing column,
  wrong dtype) is reported as a `Failure(invalid_rows=None)` rather than
  propagating — because the existing `shrink_rows`/`as_predicate` already treat
  it as "failing", and `diagnose` must preserve that. The `Failure.message`
  carries the validator's structural error text.

**Where it lives / proof.**

- `src/pycheck/failure.py` (new), `src/pycheck/ext/_adapter.py`,
  `src/pycheck/ext/{dataframely,pandera,patito}.py`, `tests/test_failure.py` (new),
  README "Explain why it fails".
- Verified: 40 tests pass; `ty check`, `ruff check`, `ruff format --check` all
  clean.

---

## Phase 1 — Repro emission + UX ✅ DONE

**Why.** A minimal repro is only useful if it's easy to *use*. Hypothesis sells
`@reproduce_failure`; minex sells "paste into a bug report with `dput()`";
pointblank sells tabular reports. pycheck currently returns a `Repro` (and now a
`Diagnosis`) and stops.

**What.**

1. `Repro.to_code() -> str` — a copy-pasteable `pl.DataFrame({...})` constructor
   (columns + dtypes preserved). `Repro.to_markdown() -> str` — the table as
   markdown for tickets. `Repro.__str__`/`__repr__` — a one-line summary
   (`removed_rows`, `predicate_calls`, `minimality_proven`).
2. A replay path: `repro.as_frame()` is trivially `repro.frame`; fold
   `Diagnosis.failure` into the printed output so a ticket reads
   "column `amount` fails `min_exclusive`; here is one row that does it."
3. A pytest helper in `pycheck.ext.pytest` (optional extra): a decorator/fixture
   that, given a validator and a fixture frame, runs the validator, and on
   failure shrinks and prints the minimal repro + rule/column instead of the raw
   traceback.

**Acceptance criteria.**

- `repro.to_code()` round-trips: `eval(repro.to_code())` is a `pl.DataFrame`
  equal to `repro.frame`.
- `to_markdown()` output renders as a table with the same dtypes.
- The pytest helper fails with a message containing the rule/column (Phase 0)
  and the minimal repro, and passes silently when the frame is valid.

**Shipped.**

- `Repro.to_code()` / `Repro.to_markdown()` / `Repro.as_frame()`, and
  `__str__` / `__repr__` summaries, in `src/pycheck/shrink.py` (formatting in
  the new `src/pycheck/_render.py`).
- `Diagnosis.to_markdown()` and `__str__` / `__repr__`, plus a compact
  `Failure.__repr__`, in `src/pycheck/failure.py`; the report reads
  "Validation failed: column `amount` fails rule `amount|min`." then the table.
- `src/pycheck/ext/pytest.py` exposing `assert_valid(frame, schema, *,
  diagnose=...)`.
- Rendering is lossless or loud: `to_code` rebuilds the frame from the exact
  literals and schema it prints and raises `TypeError` when that does not equal
  the original — no lossy code. Datetime/Duration are emitted as integer counts
  in the dtype's unit, so `ns` survives.
- **Deviation from the sketch:** the pytest helper is a plain assertion
  function (`assert_valid`), not a decorator/fixture. pytest fixture injection
  into a decorator is implicit and hard to type; a function called inside a test
  meets the acceptance criteria and stays usable in a fixture. `to_code`
  self-checks by rebuilding the frame directly, so it does not `eval` its own
  output; the `eval` round-trip is pinned by tests.
- Verified: 74 tests pass; `ty check`, `ruff check`, `ruff format --check` clean;
  `_render.py` at 100% coverage.

---

## Phase 2 — Value/boundary minimization *(closes "rows, not values")*

**Why.** The README's first limitation: `shrink_rows` drops rows, it doesn't
minimize a cell to the threshold where a `>= X`-style rule flips. Program
reducers and PBT shrinkers minimize values; the data analogue is binary-searching
a cell to the boundary.

**What.** A post-shrink step, `minimize_values(repro, fails, *, direction=None)`
— or a `values=True` flag on `diagnose` — that, for the column(s) `Failure`
flagged (or all numeric columns as fallback), binary-searches the value in each
kept row down to the smallest value that still fails the predicate.

**Contract rules.**

- Direction matters: `min`/`ge` checks shrink *down*, `max`/`le` shrink *up*,
  `isin`/`not_in` are set-membership (try each member). Without a direction the
  step must assume monotonicity and **report when it cannot** rather than
  silently returning a wrong boundary.
- This depends on Phase 0: the shrinker has no idea *which* cell matters for a
  black-box predicate. So value minimization is only safe when `Failure.column`
  is known; for the pure black-box seam, keep it out of scope or behind an
  explicit opt-in.

**Acceptance criteria.**

- For `min=0` and a row with `amount=-9`, `minimize_values` returns `amount=-1`
  (the smallest value that still fails), not `-9`, and marks it proven.

---

## Phase 3 — Column reduction *(closes "columns not built")*

**Why.** The README's second limitation. HDD reduces along input *structure*;
Perses deletes nodes against a grammar. The dataframe analogue is dropping whole
columns. **Key dependency:** a black-box `df -> bool` predicate *raises* on a
missing column, so column reduction is only tractable when we know which columns
the failing rules reference — i.e. it is a *schema-aware* feature, only reachable
after Phase 0.

**What.** `diagnose(..., columns=True)` or `shrink(frame, schema, mode="rows+columns")`:
ddmin over columns for schema-backed failures, using the rule→column map from
Phase 0 to only consider removing columns that no failing rule references (or,
more aggressively, removing a column and re-checking that the schema's *other*
rules still fail on the remainder).

**Contract rules.**

- The "frame must already match the schema's columns and dtypes" precondition
  **evolves**: for column reduction it becomes "the reducer may drop columns; it
  must not change a kept column's dtype or a rule's evaluability."
- `minimality_proven` now spans *two* dimensions (rows and columns); report each
  honestly, or report a single combined flag with a documented meaning.

**Acceptance criteria.**

- A schema with an irrelevant extra column shrinks to a frame without it, and the
  result still fails on the remaining columns.

---

## Phase 4 (deferred) — Pipeline attribution *(north-star adjacent)*

**Why not now.** "Which step introduced the bad rows" requires the pipeline graph
plus taint/provenance instrumentation (OptDebug separates data-space provenance
from code-space operation isolation; BigSift instruments Spark; BugDoc diffs
pipeline runs). It's a different product with a different core loop — worth
tracking, not worth building into a single-frame shrinker yet.

**When it makes sense.** Only after pycheck owns the "minimal repro + why" loop
end-to-end, and only as a separate package that *consumes* `pycheck` (feed each
stage's output through `diagnose` to localize the first stage whose failure
survives).

---

## Sequencing summary

| Phase | Feature | Depends on | Value | Risk |
|---|---|---|---|---|
| 0 | Failure-aware adapters + `diagnose` ✅ | — | **High** | Low–Med (shipped) |
| 1 | `to_code`/`to_markdown`/pytest helper ✅ | 0 (for the "why" text) | High | Low (shipped) |
| 2 | Value/boundary minimization | 0 | Med–High | Med (direction/monotonicity) |
| 3 | Column reduction | 0 | Med | Med–High (contract evolution) |
| 4 | Pipeline attribution | 3 | High ceiling | High (different product) |

**One rule above all:** any feature that would make `minimality_proven` a lie, or
that would swallow a validator error as "no failure," doesn't ship — it gets cut
or redesigned. That's the contract, and it's the moat.

---

## Foundation note (housekeeping, not a phase) ✅ DONE

Resolved 2026-09-27: `README.md` now matches the packaging metadata
(`requires-python = ">=3.12"`).
