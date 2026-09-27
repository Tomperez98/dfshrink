# Direct Research Notes — dataframe-contract-gaps

**Mode:** DEGRADED — direct lead-owned search (subagent fan-out failed with provider
402 in-flight/credit ceilings; see plan Verification Log).
**Date:** 2026-09-27
**Method:** web_search (Exa), fetch_content, feynman_science_database_search
(Semantic Scholar, OpenAlex), GitHub REST API, PyPI JSON.

## Exact search terms used

1. `static type checking dataframe pipelines Python pandas polars tool`
2. `data contract breaking change detection schema evolution tool`
3. `property-based testing dataframes shrinking hypothesis polars`
4. `polars streaming engine limitations unsupported operators`
5. `push down data quality constraint verification query plan optimizer`
6. `stateful streaming data validation global uniqueness referential integrity library`
7. `minimal counterexample shrinking tabular data property-based testing`
8. `abstract interpretation value constraints dataframe pipeline verification prove invariant`
9. `minimal failing dataframe counterexample shrinking tool data validation`
10. `Colnade typed dataframe polars static schema`
11. `dataframely vs patito vs pandera polars comparison`
12. `python shrink minimal failing dataframe polars delta debugging rows`
13. `data contract enforcement python library 2026 polars pandera dataframely review`
14. Semantic Scholar: `static type checking data frame libraries abstract interpretation`
15. Semantic Scholar: `bounded verification of SQL queries equivalence` (rate-limited 429)
16. OpenAlex semantic: `constraint verification data quality machine learning pipelines`

## Library evidence (PyPI JSON)

| Package | Version | Summary |
|---|---|---|
| polars | 1.44.2 | "Blazingly fast DataFrame library" |
| dataframely | 3.1.2 | "A declarative, polars-native data frame validation library" |
| patito | 0.8.6 | "A dataframe modelling library built on top of polars and pydantic." |
| pandera | 0.33.1 | "A light-weight and flexible data validation and testing tool..." |
| pointblank | 0.27.0 | "Find out if your data is what you think it is." |

## GitHub metadata (api.github.com, 2026-09-27)

| Repo | Stars | Last push | Open issues | License |
|---|---|---|---|---|
| Quantco/dataframely | 618 | 2026-09-20 | 19 | BSD-3-Clause |
| jakobgm/patito | 641 | 2026-05-08 | 52 | MIT |
| w-martin/typedframes | 13 | 2026-09-19 | 3 | none |
| akmalsoliev/Validoopsie | 91 | 2026-09-21 | 1 | MIT |

## FINDINGS BY WEDGE

### Wedge A — "Another validator" (schema/contract validation)
**Verdict: SATURATED. Do not build.**

- Posit survey (mid-2025) compares 5 polars validators: Pandera, Patito, Pointblank,
  Validoopsie, Dataframely. Each has a clear niche; the space is "truly excellent
  options" already. Great Expectations omitted: no native polars support.
  Source: https://opensource.posit.co/blog/2025-06-04_validation-libs-2025/
- dataframely (Quantco) is the polars-native leader: schema classes, primary keys,
  regex, min/max, `@dy.rule()` incl. `group_by`, schema inheritance, **collection
  validation** for related frames (referential integrity), mypy types, soft
  `filter()` with failure introspection (`counts()`, `cooccurrence_counts()`),
  and **data generation** (`Schema.sample()`). Source:
  https://dataframely.readthedocs.io/stable/guides/features/data-generation.html ,
  https://opensource.posit.co/blog/2025-06-04_validation-libs-2025/
- pandera 0.33.1: multi-backend, statistical hypothesis tests, CLI (0.33),
  Narwhals lazy backend (0.32+). Source:
  https://pandera.readthedocs.io/en/latest/polars.html
- patito: Pydantic models, reports all errors at once, `.examples()` mock data.
  Source: https://opensource.posit.co/blog/2025-06-04_validation-libs-2025/

### Wedge B — Static type checking of columns / pipelines
**Verdict: BEING ABSORBED. Narrow remaining space at the *type* level.**

- Colnade: `Column[DType]` descriptors, works with ty/mypy/pyright, Polars/Pandas/Dask,
  no plugins/codegen. Source: https://colnade.com/ , https://colnade.com/user-guide/type-checking/
- typedframes (experimental POC): descriptors + mypy/Rust static analysis for
  pandas/polars; author calls it proof-of-concept. Source: https://github.com/w-martin/typedframes
- frameright 0.3.0: ODM, Pandera runtime validation + static type checking,
  Pandas/Polars/Narwhals. Source: https://pypi.org/project/frameright/
- pavise: Protocol-based structural subtyping schemas for DataFrames.
  Source: https://github.com/kitagry/pavise
- pandera mypy integration: **pandas only**, experimental.
  Source: https://github.com/pandera-dev/pandera/blob/main/docs/source/mypy%5Fintegration.md
- Academic: abstract interpretation for *column types* is established.
  Zhuang & Lu, "Enabling Type Checking on Columns in Data Frame Libraries by
  Abstract Interpretation", IEEE Access 2022, DOI 10.1109/ACCESS.2022.3146287.
  Also shape inference for R dataframes (arXiv 2607.03889, *unverified*),
  notebook data-transform static analysis (SOAP23, lucaneg.github.io/papers/SOAP23.pdf).

### Wedge C — Value-constraint verification across a transformation DAG
**Verdict: OPEN at research grade. High ceiling, high risk.**

- Existing tools verify *types/columns*. None found that prove *value constraints*
  (ranges, uniqueness, FK) propagate through join/group_by/pivot/over **without
  executing the data**.
- Prior art exists elsewhere: VeriEQL (SMT-based bounded SQL equivalence,
  arXiv 2403.03193); "Predicate Pushdown for Data Science Pipelines"
  (Microsoft Research, 2023) — pushes *predicates*, not validation contracts.
- flowr (TypeScript) implements abstract-interpretation semantics for R data-frame
  operations (ConstraintType: OperandPrecondition/Modification/ResultPostcondition):
  https://github.com/flowr-analysis/flowr/blob/514c698d62f8eeb23cf1699286eb9eb223e1464b/src/abstract-interpretation/data-frame/semantics.ts
- polars plan introspection exists (`LazyFrame.explain`, `show_graph`, plugin API):
  https://docs.pola.rs/api/python/stable/reference/lazyframe/api/polars.LazyFrame.explain.html ,
  https://docs.pola.rs/user-guide/plugins/

### Wedge D — Streaming / stateful validation
**Verdict: REAL GAP, platform risk.**

- polars streaming: new engine since 1.31.1; unsupported ops fall back to in-memory.
  Source: https://docs.pola.rs/user-guide/concepts/streaming/ ,
  https://docs.rs/polars-stream/latest/polars_stream/fn.run_query.html ,
  tracking issue https://github.com/pola-rs/polars/issues/20947
- dataframely docs explicitly warn: on the streaming engine, lazy validation
  **aborts at the first failure** and the reported rule set is **non-deterministic
  across executions**. Source: https://dataframely.readthedocs.io/stable/guides/features/lazy-validation.html
- No library found for global uniqueness / referential integrity / windowed
  invariants **across batches** in polars.

### Wedge E — Minimal failing-dataframe shrinking (debugging)
**Verdict: OPEN, concrete, best first build. No polars/Python incumbent.**

- polars core ships *generation* only: `pl.testing.parametric.dataframes` — a
  Hypothesis strategy producing DataFrames/LazyFrames.
  Source: https://docs.pola.rs/api/python/stable/reference/api/polars.testing.parametric.dataframes.html ,
  https://docs.pola.rs/api/python/stable/reference/testing.html
- dataframely generation is "fuzzy sampling" (loop until valid) — explicitly can be
  slow/fail, and it is *not* shrinking. Source:
  https://dataframely.readthedocs.io/stable/guides/features/data-generation.html
- R has dataframe shrinking: `minex::reduce_rows()` applies `ddmin()` over rows
  preserving order, returns smallest reproducing subset.
  Source: https://rdrr.io/cran/minex/man/reduce_rows.html ,
  https://cran.rstudio.com/web/packages/minex/minex.pdf
- Python has generic (non-tabular) shrinkers only: `shrinkplz`
  (https://pypi.org/project/shrinkplz/), `carve`
  (https://github.com/nikhilcherry/carve), a ddmin skill
  (https://www.webkkk.net/Alpha-Park/genpark-iterative-delta-debugging-minimizer-skill/blob/main/README.md).
- Delta debugging background: Zeller & Hildebrandt 2002 (DOI 10.1109/32.988498);
  https://www.debuggingbook.org/html/DeltaDebugger.html
- Shrinking theory: `falsify` internal shrinking (Haskell Symposium 2023, DOI
  10.1145/3609026.3609733); https://github.com/jlink/shrinking-challenge

### Wedge F — Semantic schema drift / breaking-change detection
**Verdict: CROWDED. Avoid as standalone.**

- datalasi v0.3.0: YAML data contracts, validate pandas/polars/arrow, "gate CI on
  breaking schema changes". Source: https://pypi.org/project/datalasi/ (page fetch failed; PyPI summary via search)
- Tessera: coordinates breaking-change acknowledgements across consumers.
  Source: https://github.com/manu-7/tessera
- DriftBrake: PostgreSQL schema contract guard. Source: https://github.com/yurivski/DriftBrake
- DataHub Schema Assertions (commercial Cloud module):
  https://docs.datahub.com/docs/managed-datahub/observe/schema-assertions
- dbt-data-contracts: https://pypi.org/project/dbt-data-contracts/
- Contractual (OpenAPI/JSON Schema, not dataframes): https://contractual.dev/

### Adjacent (noted, not scored)
- `dframe-trace` — "find which pipeline step introduced nulls/dropped rows/changed
  dtype — no rules to write." Source: https://github.com/vimalnakrani08/dframe-trace
- databrickslabs/dqx — rules+streaming for PySpark, not polars.
- TFDV / Deequ lineage: Schelter et al. 2018 (Deequ, VLDB 11(12), DOI
  10.14778/3229863.3229867, cited 245); Breck et al. 2019 (TFDV, SysML/MLSys,
  cited 141, OpenAlex W2946595616).

## CORRECTIONS TO MY PRIOR ASSUMPTIONS

- I assumed "pushdown/lazy validation" was open. **dataframely already has it**
  (polars plugin, `eager=False`) — including documented streaming weaknesses.
- I assumed "generation" was open. **polars core ships Hypothesis strategies** and
  dataframely has `sample()`.
- I assumed static typing was open. **Colnade/typedframes/frameright/pandera-mypy**
  occupy it.
- The only clean gaps: (E) shrinking/minimal repro, (D) stateful streaming
  invariants, and (C) value-constraint verification (research-grade).

## UNVERIFIED / CAUTION

- Colnade, datalasi, dframe-trace, DriftBrake: small/new projects surfaced via
  web search; marketing-style pages, no independent adoption evidence. Treat as
  weak evidence.
- arXiv 2607.03889 (shape inference for R) not confirmed by ID lookup.
- Posit survey is dated mid-2025; 2026 status may differ.
