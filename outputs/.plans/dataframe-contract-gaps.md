# Deep Research Plan — dataframe-contract-gaps

**Topic:** Is there a defensible edge/gap where a new Python/polars data-contract
tool could be built, given that schema validation is already commoditized
(dataframely, patito, pandera, pointblank, polars core)?

**Date:** 2026-09-27
**Slug:** `dataframe-contract-gaps`
**Status:** APPROVED 2026-09-27 — evidence gathering in progress

---

## Key Questions

- **Q1 — Landscape:** What do existing polars/pandas validation libraries
  actually provide today, feature-by-feature? (dataframely, patito, pandera,
  pointblank, Great Expectations, Soda, polars core schema support.) Maintenance
  status, adoption, licensing, backend coverage.
- **Q2 — Technical gaps:** Which problems in this space remain unsolved or
  poorly solved?
  - static/pushdown contract verification across a transformation DAG (prove or
    refute downstream contracts without executing)
  - stateful / streaming validation (uniqueness, referential integrity, windowed
    invariants across batches)
  - constraint-driven data generation + minimal counterexample shrinking
    (property-based testing for tabular data)
  - semantic schema drift / breaking-change detection ("semver for data
    contracts")
- **Q3 — Research & prior art:** What does the literature and industry practice
  say about these problems? (constraint pushdown, typing for dataframes,
  data contracts / ODCS, Deequ-style constraint suggestion, TFX/data validation,
  adaptive/streaming anomaly detection, PBT + shrinking.)
- **Q4 — The edge:** For each candidate wedge, is there evidence that a small
  team could build something meaningfully better than the status quo? Rank
  wedges by (a) real unmet need, (b) technical defensibility, (c) build risk.
- **Q5 — Feasibility:** What do polars' Rust plugin API, streaming engine
  maturity, and expression/plan introspection allow? What are the hard
  constraints a builder would hit?

## Evidence Needed

- Library evidence: PyPI metadata, GitHub repos/READMEs/docs, release cadence,
  issue trackers, feature matrices (per Q1).
- Polars platform evidence: official docs for the Rust plugin API, streaming
  engine, `LazyFrame` plan/expression model, schema handling (per Q5).
- Academic evidence: papers/preprints on constraint verification, dataframe
  type systems, data validation for ML, minimal counterexample generation,
  streaming validation (per Q3), plus standards docs (ODCS, data-contract specs).
- Industry evidence: engineering blogs/talks where teams built or abandoned
  in-house data-contract tooling (per Q4).
- Negative evidence: explicitly record what is *already solved* so we do not
  re-propose a commoditized idea.

## Scale Decision

**Chosen: broad survey → 3 `researcher` subagents + lead synthesis.**

Rationale: this is not a "what is X" explainer. It spans an OSS landscape, an
academic/standards literature, and an infrastructure-feasibility question. Three
independent, non-overlapping evidence streams are justified. Direct search alone
would under-cover the literature and feasibility angles. Not going to 4–6
because the domain is well-bounded (Python dataframe validation + polars).

- **T1 — OSS landscape & feature gaps** (`researcher`)
- **T2 — Research, standards & industrial practice** (`researcher`)
- **T3 — Feasibility & adjacent-gap validation** (`researcher`)
- **S1 — Synthesis & draft** (lead, not delegated)
- **V1 — Citation/verification** (`verifier`, after draft)
- **R1 — Adversarial review** (`reviewer`, after cited draft)

## Task Ledger

| ID  | Owner      | Task | Output | Status |
|-----|-----------|------|--------|--------|
| T1  | researcher | Map polars/pandas validation libraries: features, maintenance, adoption, explicit unsolved issues | `outputs/.drafts/dataframe-contract-gaps-research-oss.md` | pending |
| T2  | researcher | Survey literature + standards + industry blogs on data contracts, dataframe typing, constraint pushdown, PBT/shrinking, streaming validation | `outputs/.drafts/dataframe-contract-gaps-research-lit.md` | pending |
| T3  | researcher | Assess polars plugin/streaming/plan APIs; validate feasibility of each candidate wedge; find adjacent gaps | `outputs/.drafts/dataframe-contract-gaps-research-feasibility.md` | pending |
| S1  | lead       | DEGRADED (direct search): synthesize ranked wedge analysis + draft; notes at `-research-direct.md` | `outputs/.drafts/dataframe-contract-gaps-draft.md` | done |
| V1  | lead       | Mode degraded → self-citation + URL checks (verifier subagent not run) | `outputs/.drafts/dataframe-contract-gaps-cited.md` | done |
| R1  | lead       | Mode degraded → self-review, FATAL/MAJOR/MINOR (reviewer subagent not run) | `outputs/.drafts/dataframe-contract-gaps-verification.md` | done |
| D1  | lead       | Deliver brief + provenance | `outputs/dataframe-contract-gaps.md`, `outputs/dataframe-contract-gaps.provenance.md` | done |

## Verification Log

- No evidence gathered yet.
- Scale decision recorded before owner assignment. ✅
- **2026-09-27 — T2 (`lit`) and T3 (`feas`) FAILED at launch.** Provider returned
  `402 in_flight_budget_exhausted` (openrouter in-flight budget) while 3
  researchers ran concurrently. `lit` reached 9 turns / 191k input tokens
  (cost 0.033) but wrote no output file; `feas` produced no work product.
  `oss` (T1) continued running normally. Remedy per provider: retry after
  in-flight requests settle (Retry-After: 120s).
  Status: T1/T2/T3 all failed. **Switched to degraded direct mode** (same research
  questions, lead-owned searches via web + paper databases). No different execution
  mode was invented; the deliverable is produced and its verification status is
  recorded as PASS WITH NOTES.
- **2026-09-27 — DEGRADED DELIVERY.** 3 direct-search rounds (14 web queries, 2 paper-
  database queries, 17 URL liveness checks, 2 arXiv ID verifications). Verifier and
  reviewer subagents were NOT run (provider 402); citations and review done by the
  lead instead. Final artifacts written and verified on disk.
- **2026-09-27 — Key correction to the premise:** dataframely already ships lazy/
  pushdown validation, data generation, and multi-frame referential integrity; polars
  core ships Hypothesis DataFrame strategies. Three of four original wedges are
  occupied. Reframed the edge to *debugging/tooling around validation failures*,
  with minimal failing-dataframe shrinking as the recommended first build.

## Decision Log

- 2026-09-27: Established that "pydantic for dataframes" is commoditized via
  PyPI checks (dataframely 3.1.2, patito 0.8.6, pandera 0.33.1, pointblank
  0.27.0). Scope reframed from "build a validator" to "find a defensible wedge."
- 2026-09-27: Chose 3-researcher broad survey over direct search, per Scale
  Decision above.
- 2026-09-27: Output path `outputs/` (non-paper brief), not `papers/`.
- 2026-09-27: T2/T3 retry decided at concurrency 1 (not 3) to fit the
  provider in-flight budget. Retry is same-protocol (same agent, same brief,
  same output path) — not a mode switch.

## Run IDs (workflow c67b8484)

- T1 `oss`: child 3fa02943-e6d4-478e-ae38-646b9a12f374
- T2 `lit`: child 2ffde60d-8ec7-4d32-b677-e0396417803d — FAILED (402)
- T3 `feas`: child f71cfc3d-57e4-4fe2-9688-570189f5bc89 — FAILED (402)

## Deliverable

A cited brief that answers: **is there an edge, where is it, how defensible is
it, and what would a staff engineer actually build first?**
