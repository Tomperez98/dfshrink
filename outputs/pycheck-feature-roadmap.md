# What to Add to pycheck — a Smart, Valuable Tool on Top of the Shrinking Core

Date: 2026-09-27 · Status: cited draft · All cited URLs surfaced via direct fetch or web search on 2026-09-27

---

## Executive summary

`pycheck` is a small, well-made library that turns a failing Polars `DataFrame`
into the minimal row-subset that still breaks a `DataFrame -> bool` predicate,
using delta debugging (`ddmin`) [1][2]. Its own README names the natural
extension surface, and that list is the honest starting point: it shrinks **rows
only**, does not **minimize values** to a boundary, does not **reduce columns**,
and does not do **pipeline attribution** [2].

The single highest-value addition is not another shrinker feature — it is
**making the adapters failure-aware**. Every validator pycheck adapts already
exposes *which rules failed, on which columns, and which rows/values are
invalid*: dataframely's `FailureInfo` (`counts()`, `cooccurrence_counts()`,
`invalid()`) [6][7][8][9]; pandera's `SchemaErrors.failure_cases` and `.data`
[10][11]; patito's per-column error detail [12]. Today pycheck inverts
`is_valid`/`validate` to a bare `bool` and throws all of that away, then
re-derives "which rows fail" by black-box ddmin at ~log₂(n) predicate calls [1][2].
Surfacing that metadata does two things at once: it **explains why** the repro
fails (rule + column, not just rows), and it can **skip or seed the shrink**
entirely.

That is the coherent "smart tool": keep the black-box predicate as the *fallback*
seam, but let the adapters exploit structured failure info when it exists. Around
that core sit three cheaper, compounding additions — **column reduction**,
**value/boundary minimization**, and a **repro-emission/UX layer** (a
copy-pasteable constructor, a pytest plugin, a pretty-printed report) [13][14]
[15]. Pipeline attribution is real prior art but a different, heavier product;
defer it [16][17][18].

## Q1. Confirm the gaps (from the code, the primary evidence)

The README's "When not to use it" list is accurate and already captures the
extension surface [2]:

- **Rows, not values.** `shrink_rows` drops rows; it never touches a cell to
  find the threshold where a `>= X`-style predicate flips [2].
- **Column reduction isn't built.** `_reduce_once` partitions row indices only;
  columns are carried through unchanged (`_take_rows` selects rows by position)
  [1].
- **No pipeline attribution.** Nothing in `shrink.py` knows about upstream steps
  [1][2].
- **Needs a pure, deterministic predicate.** The docstring notes that `ddmin`
  never re-tests a subset, so there is no memoization — correct for row-only
  ddmin, and a deliberate design choice [1].

These are confirmed as *deliberate scope decisions*, not bugs. The contract a
new feature must not break: `shrink_rows(frame, fails, *, max_evals) ->
Repro | None`, where `Repro.frame` still fails, has ≥1 row, preserves original
row order, and (when `minimality_proven`) is 1-minimal [1].

## Q2. Minimization extensions (what the reduction literature offers)

The test-reduction literature is mature and points at exactly three extensions
pycheck lacks, none of which is tabular in the prior art:

- **Column reduction ← HDD / Perses.** Hierarchical Delta Debugging guides
  reduction by the *tree structure* of the input [3]; Perses deletes/hoists
  syntax nodes against a grammar [4]. The dataframe analogue is reducing the
  *schema* — dropping whole columns, then (later) expressions inside a lazy
  plan. R's `minex` reduces both *statements* and *rows* [14]; pycheck has only
  the row half [1]. No Python/Polars tool was found that reduces columns; this
  is open.
- **Value / boundary minimization.** Program reducers and PBT shrinkers minimize
  values (Hypothesis; `falsify`; "Evaluating Shrinking" 2026) [5][19]. For data
  this is the cheap, high-value cousin of row-shrinking: once `shrink_rows` has
  isolated one bad row, binary-search the cell(s) of interest to find the
  smallest value that still fails — e.g. the exact `amount` where `min` breaks.
  This is the most concrete "rows, not values" gap [2].
- **Test-outcome caching.** HDD work caches outcomes [20]. This only matters once
  pycheck reduces structure (columns/values) where a candidate may be re-tested;
  for pure row-ddmin the existing "no memoization" note is correct [1][2]. So
  caching is a *consequence* of adding column/value reduction, not an
  independent feature to add first.

Multi-bad-row isolation (finding *all* distinct failing rows, not one minimal
repro) is another candidate, but it is better served by Q3's failure metadata
than by repeated ddmin [6][7].

## Q3. The "explain why" core (the smart-tool thesis)

Every adapted validator already knows *why* a frame fails. pycheck discards it:

- **dataframely** — `Schema.filter(df)` returns `(valid, FailureInfo)`, where
  `FailureInfo.counts()` maps each rule to its failure count (e.g.
  `{'amount|min_exclusive': 1}`), `FailureInfo.cooccurrence_counts()` reports
  rules that fail together, and `FailureInfo.invalid()` returns the actual
  invalid rows [6][7][8][9].
- **pandera** — `validate(lazy=True)` raises `SchemaErrors` whose `.message`
  carries per-error `{schema, column, check, error}` entries and whose
  `.failure_cases` is a frame of (column, check, check_number, failure_case,
  index); `.data` is the failing frame [10][11].
- **patito** — `DataFrameValidationError` carries per-column rule names, affected
  values, and error types (e.g. "product_id — 2 rows with duplicated values")
  [12].

The consequence is concrete: the current adapters reduce this to `True`/`False`
and then `shrink_rows` re-discovers the failing rows with ~log₂(n) predicate
evaluations [1]. A failure-aware adapter can (a) return `FailureInfo.invalid()` /
`failure_cases` directly as the repro — no shrinking needed when the validator
tells you the rows — and (b) annotate the result with the failing **rule** and
**column**, turning "here are 3 rows" into "column `amount` fails rule
`min_exclusive`, and here is one row that does it." Pointblank already ships the
"collect extracts of failing rows" concept [13]; the differentiator is
*minimality* — the smallest failing extract, not just any.

**Inference (flagged):** the cost/benefit of the failure-aware path is argued
from the documented API shapes above [6][7][10][12], not from a benchmark.

## Q4. Pipeline attribution — a different product, defer

"Which join/cast introduced the bad rows" is real prior art, but it is a
pipeline-level problem, not a single-frame one: OptDebug isolates
fault-inducing operations in dataflow applications and explicitly separates
data-space (provenance) from code-space (operation isolation) [16]; BigSift does
fault isolation in Spark [17]; BugDoc explains differences between pipeline runs
[18]. All require the pipeline graph plus instrumentation or provenance capture.
That is a heavier, separate tool — record it as the north-star adjacent, not the
next add.

## Q5. Tool surface / UX (cheap, high-leverage)

Analogues show what turns a function into a tool:

- **Hypothesis** persists failures and replays them (`@example`,
  `@reproduce_failure`) and prints "Falsifying example: ..." — the analogue for
  pycheck is emitting a copy-pasteable `pl.DataFrame({...})` constructor for the
  minimal repro, plus a replay/seed path so a shrinking result is reproducible
  [15].
- **minex** sells its output as "small enough to paste into a bug report with
  `dput()`" [14].
- **Pointblank** renders stakeholder-friendly tabular reports [13].

For pycheck this means: a `Repro.to_code()`/`Repro.to_markdown()` (ticket-ready
repro), a pytest helper, and optionally a CLI. Low risk, compounds with Q3.

## Q6. Sequencing and the coherent tool

Recommended order, cheapest-to-highest-value ratio first:

1. **Failure-aware adapters (Q3)** — the flagship "smart" move. Exploit
   `FailureInfo` / `failure_cases` / patito error detail to explain *why* and to
   short-circuit shrinking. Complements — never breaks — the black-box seam
   [6][7][10][12].
2. **Repro emission + pytest/UX layer (Q5)** — cheap, makes every result useful
   in a ticket or test immediately [14][15].
3. **Value/boundary minimization (Q2)** — closes "rows, not values"; needs
   careful contract design (a `Repro` plus a `minimized_values` step) [2][5].
4. **Column reduction (Q2)** — closes "columns not built"; schema-guided,
   HDD/Perses-flavoured; the largest algorithmic lift of the in-scope set [3][4].
5. **Defer: pipeline attribution (Q4)** — different product [16][17][18].

The coherent "smart and valuable tool" is: *a failure-shrinking library that,
given a frame and a validator, returns the smallest failing subset **and** the
rule/column that failed, as a pasteable repro — using the validator's own
failure metadata when it has any, and falling back to black-box delta debugging
when it doesn't.*

## Evidence-backed caveats and disagreements

- **"No tool found" ≠ "no tool exists."** Column reduction and value
  minimization were assessed by search, not exhaustive audit — the same caveat
  the prior brief recorded [21].
- **Failure-metadata availability differs per validator.** dataframely's
  `FailureInfo` and pandera's `failure_cases` are richer than a bare
  `is_valid`/`validate` bool; the fallback predicate remains necessary for
  custom predicates and for validators that only expose a bool [6][10][12].
- **The ecosystem is consolidating.** dataframely and pandera could absorb
  "minimal failing-row extract" cheaply (dataframely already ships
  `FailureInfo.invalid()`; pointblank ships failing-row extracts). pycheck's
  edge is *minimality + black-box generality*, not mere failure listing — so the
  failure-aware adapter must still prove/return minimality, or the edge erodes
  [6][13].
- **`ddmin` cost is predicate-bound.** The ~log₂(n) figure only holds for the
  common "few bad rows" case; when the failure needs most of the frame, the
  budget stops the search (already documented in pycheck) [1][2].

## Open questions

1. How much of dataframely's `FailureInfo.invalid()` can be trusted as *minimal*
   (it lists all invalid rows, not a 1-minimal subset) — and does pycheck still
   need to ddmin *within* the invalid set to promise its current contract? [6][7]
2. Value minimization requires knowing *which* column/cell matters; without
   Q3's metadata the shrinker has no target. Is value-minimization only viable
   as a follow-on to the failure-aware adapter?
3. Column reduction can change dtypes (a column's absence may make a rule
   structurally un-evaluable) — how should the "frame must already match the
   schema" precondition evolve? [2]
4. Is there real demand for minimal repros in data pipelines vs. software tests
   (the prior brief's unanswered demand question still stands)? [21]
5. Would dataframely/pandera absorb minimal-failure extraction, closing the
   wedge (same open question as the prior brief, now sharper)? [21]

## Sources

**Primary (local, read directly):**
1. `src/pycheck/shrink.py` — the ddmin implementation and its contract docstring (local, this repo).
2. `README.md` — the "What it does" / "When not to use it" / "The contract" sections (local, this repo).

**Literature (via Semantic Scholar / OpenAlex, DOIs authoritative):**
3. Misherghi & Su — *HDD: Hierarchical Delta Debugging*, ICSE 2006 — DOI 10.1145/1134285.1134307 — https://doi.org/10.1145/1134285.1134307
4. Sun et al. — *Perses: Syntax-Guided Program Reduction*, ICSE 2018 — DOI 10.1145/3180155.3180236 — https://doi.org/10.1145/3180155.3180236
5. Keleş, Miao & Lampropoulos — *Evaluating Shrinking (Experience Report)*, 2026 — DOI 10.1145/3830439.3831271 — https://doi.org/10.1145/3830439.3831271
19. *falsify: Internal Shrinking Reimagined for Haskell*, Haskell Symposium 2023 — DOI 10.1145/3609026.3609733 (via prior brief [21])
20. Hodován, Kiss & Gyimóthy — *Tree Preprocessing and Test Outcome Caching for Efficient HDD*, 2017 — DOI 10.1109/AST.2017.4 — https://doi.org/10.1109/AST.2017.4

**Validator failure-metadata APIs (fetched / search-verified):**
6. dataframely — `FailureInfo.counts` — https://dataframely.readthedocs.io/stable/api/filter_result/_gen/dataframely.FailureInfo.counts.html
7. dataframely — `FailureInfo.cooccurrence_counts` — https://dataframely.readthedocs.io/latest/api/filter_result/_gen/dataframely.FailureInfo.cooccurrence_counts.html
8. dataframely — `Schema.filter` (soft-validation, returns `(valid, FailureInfo)`) — https://dataframely.readthedocs.io/latest/api/schema/_gen/dataframely.Schema.filter.html
9. dataframely — real-world example (failure introspection: `failure.counts()`) — https://dataframely.readthedocs.io/stable/guides/examples/real-world.html
10. pandera — *Data Validation with Polars* (SchemaError/SchemaErrors, `.failure_cases`, `.data`) — https://pandera.readthedocs.io/en/stable/polars.html
11. pandera — *Lazy Validation* (`SchemaErrors.message`, `failure_cases`) — https://pandera.readthedocs.io/en/stable/lazy_validation.html
12. patito — README (`DataFrameValidationError` per-column detail) — https://github.com/JakobGM/patito/blob/main/README.md

**Analogue UX / tools:**
13. Pointblank — *Validation Reports* (failing-row extracts, tabular reports) — https://posit-dev.github.io/pointblank/user-guide/post-interrogation/validation-reports.html
14. minex — `reduce_rows()` (row + statement ddmin, `dput()` output) — https://rdrr.io/cran/minex/man/reduce_rows.html
15. Hypothesis — *Replaying Failures* (`@example`, `@reproduce_failure`, ExampleDatabase) — https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html

**Pipeline attribution prior art (deferred scope):**
16. OptDebug — *Fault-Inducing Operation Isolation for Dataflow Applications* (SOCC 2021) — https://people.cs.vt.edu/~gulzar/assets/pdf/optdebug_socc21.pdf
17. BigSift — *Automated Debugging in Data-Intensive Scalable Computing* — https://www.vanbastelaer.com/publication/bigsift/bigsift.pdf
18. BugDoc — *Iterative debugging and explanation of pipelines*, VLDB J 2023 — DOI 10.1007/s00778-022-00733-5 — https://dl.acm.org/doi/10.1007/s00778-022-00733-5

**Secondary (context):**
21. Prior brief — `outputs/dataframe-contract-gaps.md` (this repo) — mapped the validator ecosystem and recommended shrinking as "wedge E".
