# Research Notes (direct mode) — pycheck-feature-roadmap

Mode: direct search, lead-owned (no researcher subagents). Date: 2026-09-27.

## Exact search terms / tool calls used

### Literature (feynman_science_database_search)
1. semanticscholar: "hierarchical delta debugging test case minimization"
2. semanticscholar: "Perses syntax-guided program reduction"
3. openalex (semantic): "property-based testing shrinking counterexample minimization"

### Web (web_search, queries grouped)
- Group A (validator failure metadata): "dataframely filter failure
  introspection counts cooccurrence_counts" · "pandera failure_cases lazy
  validation error report polars" · "patito DataFrameValidationError error
  details rows"
- Group B (attribution / lineage): "data lineage taint tracking which
  transformation introduced bad rows dataframe" · "delta debugging pipeline
  attribution data provenance bad rows" · "Hypothesis minimal counterexample
  reproduce output"
- Group C (analogue UX / shrinking): "minex reduce_rows R minimal failing
  rows" · "delta debugging dataframe column reduction minimize columns" ·
  "pointblank data validation report HTML interactive"

### Direct fetches (fetch_content)
- https://raw.githubusercontent.com/Quantco/dataframely/main/README.md
- https://pandera.readthedocs.io/en/stable/polars.html
- https://pandera.readthedocs.io/en/stable/lazy_validation.html
- dataframely FailureInfo API pages (via web_search "dataframely filter failing
  rows counts cooccurrence_counts introspection"): `FailureInfo.counts()`,
  `FailureInfo.cooccurrence_counts()`, `FailureInfo.invalid()`, `Schema.filter()`.

### Local (primary)
- src/pycheck/shrink.py, src/pycheck/ext/*, README.md, tests/, prior brief
  outputs/dataframe-contract-gaps.md.

## Findings by theme

### Theme 1 — Minimization tool landscape (Q2)

- **HDD** (Misherghi & Su, 2006, DOI 10.1145/1134285.1134307, 319 cites): delta
  debugging guided by the *tree structure* of the input. The dataframe analogue
  is schema/column structure — i.e. reducing columns, not just rows.
- **Modernizing HDD** (Hodován & Kiss 2016, DOI 10.1145/2994291.2994296);
  **HDDr** (Kiss et al. 2018, DOI 10.1145/3278186.3278189).
- **Tree Preprocessing and Test Outcome Caching for Efficient HDD** (Hodován et
  al. 2017, DOI 10.1109/AST.2017.4): caching test outcomes. Relevant only once
  pycheck reduces *structure* (columns/values) where subsets may be re-tested;
  current pure-row ddmin never re-tests, so caching is currently unnecessary
  (and pycheck's docstring says so — consistent).
- **Perses** (Sun et al. 2018, DOI 10.1145/3180155.3180236, 159 cites):
  syntax-guided reduction — delete/hoist AST nodes per a grammar. Analogue:
  schema-guided reduction over columns/expressions. Successors: T-Rec (2024),
  Ad Hoc Syntax-Guided Program Reduction (2023), DRReduce (2026) — all program
  reduction, none tabular.
- **Hypothesis shrinking** (PBT): internal shrinking; `falsify` (Haskell Symp
  2023, DOI 10.1145/3609026.3609733, from prior brief); "Evaluating Shrinking"
  (Keleş et al. 2026, DOI 10.1145/3830439.3831271) — experience report on
  shrinking quality. "Shrinking Counterexamples with Genetic Algorithms" (Lo et
  al. 2020). None target tabular/foreign-key data.
- **minex** (R): `reduce_rows()` = row-level ddmin preserving order, returns
  minimal subset for `dput()` pasting. ALSO reduces failing R *scripts*
  (statement-level ddmin), each candidate in a **separate R process**. pycheck
  is the Python/Polars row-reducer; it does not do statement/expression
  reduction (that maps to column/expression reduction, a gap).
- **Delta debugging base** (Zeller & Hildebrandt 2002, DOI 10.1109/32.988498) —
  already cited in pycheck's source.

### Theme 2 — Validator failure metadata (Q3, the "explain why" core)

- **dataframely** `Schema.filter(df, cast=True)` returns `(valid, FailureInfo)`.
  `FailureInfo.counts() -> {rule_name: n}`, `FailureInfo.cooccurrence_counts()
  -> {frozenset[rule_names]: n}`, `FailureInfo.invalid() -> DataFrame` (the
  actual invalid rows). So dataframely already exposes *which rules* failed and
  *which rows* — pycheck's dataframely adapter currently calls `is_valid()` and
  inverts to a bare bool, discarding all of this.
- **pandera**: `validate()` raises `SchemaError`; `validate(lazy=True)` raises
  `SchemaErrors` with `.message` (SCHEMA/DATA sections, each entry = {schema,
  column, check, error}) and `.failure_cases` (a DataFrame: schema_context,
  column, check, check_number, failure_case, index) and `.data` (the failing
  frame). pandera exposes the failing column + check + example failure cases.
  pycheck's pandera adapter catches the error and returns `True`, discarding it.
- **patito**: `DataFrameValidationError` prints human-readable per-column
  details, e.g. "product_id 2 rows with duplicated values (type=value_error.
  rowvalue)" and "temperature_zone Rows with invalid values: {'oven'}". The
  exception object carries rule + column + affected values + error type.
- **Pointblank**: `interrogate(collect_extracts=True)` (default) collects
  *extracts of failing rows*; `get_step_report()`, `get_tabular_report()`
  render rich tables. Failing-row extraction is already a shipped concept there.
- Net: the three validators pycheck adapts all expose *structured failure
  metadata* (failing rules, columns, invalid rows/values). pycheck currently
  re-derives "which rows fail" by black-box ddmin at ~log₂(n) cost when the
  validator could have told it directly. That inversion is the single biggest
  "smart tool" opportunity.

### Theme 3 — Attribution / lineage (Q4)

- **OptDebug** (SOCC 2021): isolates *fault-inducing operations* in dataflow
  applications; explicitly distinguishes data-space (provenance) vs code-space
  (operation isolation). Heavyweight: needs the pipeline graph + instrumentation.
- **BigSift** (Automated Debugging in DISC): fault isolation in Spark.
- **BugDoc** (VLDB J 2023, DOI 10.1007/s00778-022-00733-5): iterative debugging
  + explanation of pipelines; derives explanations of differences between
  pipeline runs.
- **Provenance-guided rollback** (TPLP): Datalog provenance for explanations.
- Net: pipeline attribution is a *different product* (pipeline graph + taint +
  instrumentation), not a natural extension of a single-frame shrinker. Defer;
  record as future/north-star adjacent.

### Theme 4 — UX analogues (Q5)

- **Hypothesis**: persists failures in `ExampleDatabase`; replay via `@example`
  or `@reproduce_failure(...)`; emits "Falsifying example: ..." snippets.
  Analogue: pycheck should emit a copy-pasteable repro (a `pl.DataFrame({...})`
  constructor) and a replay/seed mechanism.
- **minex**: results "small enough to paste into a bug report with `dput()`".
- **Pointblank**: stakeholder-friendly tabular reports.
- Net: repro-snippet emission + pytest plugin + pretty-print are cheap,
  high-leverage UX additions on top of the existing core.

## Inferences (flagged as such in the draft)

- "Column reduction / value minimization are genuinely absent in the Python/
  Polars ecosystem" is inferred from search coverage, not an exhaustive audit —
  same caveat as the prior brief ("no tool found ≠ no tool exists").
- The exact cost profile of a failure-aware adapter is inferred from API shapes,
  not measured.
