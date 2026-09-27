# T3 Brief — Feasibility & adjacent-gap validation

You are the **T3** researcher for the deep research run `dataframe-contract-gaps`.
Write your findings to `outputs/.drafts/dataframe-contract-gaps-research-feasibility.md`.

## Mission

Determine what is *technically buildable* on today's polars, and stress-test
each candidate wedge for feasibility and defensibility. Be adversarial: your job
is to find reasons a proposed wedge would NOT work or is NOT novel.

## Candidate wedges to assess

1. **Static/pushdown contract verification across a transformation DAG**
   (propagate column-level constraints through join/group_by/pivot/over; prove
   or refute downstream contracts without collecting).
2. **Stateful / streaming validation** (global uniqueness, referential
   integrity, windowed invariants across batches).
3. **Constraint-driven generation + minimal counterexample shrinking**
   (property-based testing for dataframes with FK-aware shrinking).
4. **Semantic schema drift / breaking-change detection** ("semver for data
   contracts" — renamed/narrowed/relaxed columns, not just equality).
5. Any stronger wedge you discover that we missed.

## Questions to answer with evidence

- **Polars platform capabilities (cite official docs):**
  - Rust plugin API (`pyo3-polars`): what can it do, what are its limits?
  - Expression / plan model: can you introspect a `LazyFrame` plan
    (`explain`, `.meta`) programmatically and reliably? Stability?
  - Streaming engine: maturity, operator coverage, known limitations.
  - Schema handling: `pl.Schema`, `collect(schema=...)`, `scan_*` schema args,
    strict casting behavior.
  - Are there optimizer hooks / extension points for pushing custom
    constraints?
- **Feasibility per wedge:** required machinery, Python vs Rust, main risks,
  estimated surface area (small/medium/large).
- **Novelty per wedge:** search for any existing tool/paper that already does
  it. If one exists, say so and downgrade the wedge. (Cross-check T1 concerns
  but do your own search.)
- **Wedge scoring:** a table with columns: wedge | unmet need (evidenced) |
  technical defensibility | build risk | existing competition | verdict.

## Method

- Use official polars documentation (pola.rs docs, API reference, blog posts)
  and the polars GitHub repo. Use web search + fetch.
- Use paper search where novelty is in question.
- Verify API claims against current docs; do not rely on memory or older
  versions.
- Mark anything you could not verify as "unverified".

## Output format

`outputs/.drafts/dataframe-contract-gaps-research-feasibility.md`:

- **Polars platform capability notes** with doc URLs.
- **Wedge feasibility assessment** (one subsection each).
- **Wedge scoring table**.
- **Recommended wedge** with rationale and the strongest counterargument.
- Full **source list** with URLs.

Every claim needs a source URL. Distinguish verified facts from inference.
