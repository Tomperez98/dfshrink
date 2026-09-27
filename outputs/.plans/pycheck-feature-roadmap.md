# Deep Research Plan — pycheck-feature-roadmap

**Topic:** Given `pycheck` (a ddmin-based Polars failure-shrinking library, the
"wedge E" this repo's prior brief recommended building), what makes sense to add
next, and how do we turn it into a smart, valuable tool that fits what already
exists?

**Date:** 2026-09-27
**Slug:** `pycheck-feature-roadmap`
**Status:** DRAFT — awaiting approval

---

## Context already established (primary, local evidence)

The library is fully read. In one sentence: `shrink_rows(frame, fails)` runs
delta debugging (`ddmin`, Zeller & Hildebrandt 2002) over a Polars frame's rows
and returns the minimal row-subset that still fails a `DataFrame -> bool`
predicate, with optional adapters that invert `is_valid`/`validate` for
dataframely, pandera, and patito.

The README's own "When not to use it" section names the natural extension
surface — the most authoritative statement of what is *not* yet built:

1. **"Rows, not values."** It drops rows; it does not minimize a cell to a
   boundary value.
2. **"Column reduction isn't built."** Only rows are reduced; columns are kept.
3. **"No pipeline attribution."** It won't tell you *which step* (join, cast)
   introduced the bad rows.
4. **"Needs a pure, deterministic predicate."** Nondeterminism makes shrinking
   meaningless.

The prior brief (`outputs/dataframe-contract-gaps.md`) already mapped the
validator ecosystem (dataframely, pandera, patito, pointblank, Validoopsie) and
recommended shrinking as the first build; the north star it set was
value-constraint verification over a transformation DAG ("wedge C").

## Key Questions

- **Q1 — Gap confirmation.** Which of the four README limitations (value
  minimization, column reduction, pipeline attribution, nondeterminism handling)
  are real, buildable gaps vs. deliberate scope decisions? What does the
  current `Repro`/`shrink_rows` contract already cover that a new feature must
  not break?
- **Q2 — Minimization extensions.** What does the delta-debugging /
  test-reduction tool landscape (ddmin successors, HDD, Perses, C-Reduce,
  Hypothesis shrinking, falsify, minex, shrinkplz, carve) offer that pycheck
  lacks — column reduction, boundary/value minimization, multiple-bad-row
  isolation, memoization/caching, sampling/parallelization for large frames?
  Which are worth adding, at what cost and risk to the ~log₂(n) guarantee?
- **Q3 — The "explain why" angle (the smart-tool core).** What failure metadata
  do the adapted validators expose (dataframely `counts()` /
  `cooccurrence_counts()` / `filter()` failure introspection; pandera
  failure-cases / lazy errors; patito error details) that pycheck currently
  throws away when it inverts `is_valid`/`validate` to a bare `bool`? How could
  pycheck surface the *reason* a repro fails — the failing rule and column —
  not just the rows?
- **Q4 — Attribution / blame.** What does "which pipeline step introduced these
  rows" look like in practice (data lineage, taint tracking, provenance)? Is it
  feasible to layer onto pycheck's adapter seam, or is it a different product?
- **Q5 — Tool surface / UX.** What turns a function into a smart, valuable
  *tool*: pytest plugin, CLI, ticket-ready/pretty-printed repro, rich
  notebook output, caching, output formats? What do analogues (Hypothesis repro
  output, pointblank reports, minex, shrinkplz, carve) do for UX that pycheck
  could borrow?
- **Q6 — Differentiation & sequencing.** What could incumbents (dataframely /
  pandera) absorb cheaply and close pycheck's edge? What is the single
  highest-value, lowest-risk first addition, and what is the coherent "smart
  tool" it compounds into?

## Evidence Needed

- **Primary (already gathered):** `src/pycheck/shrink.py`,
  `src/pycheck/ext/*`, `README.md`, `tests/`, prior brief
  `outputs/dataframe-contract-gaps.md`. Treat these as authoritative.
- **Minimization tools + literature:** ddmin (have), Hierarchical Delta
  Debugging, Perses, C-Reduce, Hypothesis shrinking internals, falsify, minex,
  shrinkplz, carve. Feature inventory relevant to Q2.
- **Validator failure-metadata APIs:** dataframely failure-introspection
  (`counts`, `cooccurrence_counts`, `filter`), pandera failure cases / lazy
  error structure, patito `DataFrameValidationError` contents. Relevant to Q3.
- **Attribution/lineage:** existing "bad-row blame", data lineage, and taint
  approaches. Relevant to Q4.
- **UX of analogues:** Hypothesis repro output, pointblank report format,
  minex output shape. Relevant to Q5.
- **Negative evidence:** record what is already solved or deliberately
  out-of-scope so we do not re-propose it.

## Scale Decision

**Chosen: direct search, lead-owned. No researcher subagents.**

Rationale (recorded before owner assignment):

1. **The primary evidence is local and already gathered.** The subject is a
   small, fully-read codebase plus a prior brief that already mapped the
   surrounding ecosystem. The research question is anchored, not a
   green-field landscape scan.
2. **Demonstrated provider ceiling in this repo.** The prior run
   (`dataframe-contract-gaps`) launched 3 `researcher` subagents; all three
   failed with `402 in_flight_budget_exhausted`, forcing degraded direct mode.
   Re-spawning 3 researchers risks the same ceiling and wastes the run.
3. **External evidence is supplementary and well-bounded** to three themes
   (minimization tools, validator failure-metadata, attribution/UX), each
   coverable with 1–2 query groups + paper search.

I will commit to **≥3 distinct query groups** across the three themes, record
the exact search terms in `outputs/.drafts/pycheck-feature-roadmap-research-direct.md`,
and self-cite/self-review (no `verifier`/`reviewer` subagents — consistent with
direct-search mode).

## Task Ledger

| ID  | Owner | Task | Output | Status |
|-----|-------|------|--------|--------|
| T0  | lead  | Read code, README, tests, prior brief | (context only) | done |
| T1  | lead  | Minimization-tool landscape: column/value reduction, HDD, Perses/C-Reduce, Hypothesis, falsify, minex/shrinkplz/carve | `-research-direct.md` | pending |
| T2  | lead  | Validator failure-metadata APIs (dataframely/pandera/patito) for the "explain why" angle | `-research-direct.md` | pending |
| T3  | lead  | Attribution/lineage + analogue UX (Hypothesis, pointblank, minex) | `-research-direct.md` | pending |
| S1  | lead  | Synthesize ranked roadmap + draft | `outputs/.drafts/pycheck-feature-roadmap-draft.md` | pending |
| C1  | lead  | Self-cite + URL verification | `outputs/.drafts/pycheck-feature-roadmap-cited.md` | pending |
| R1  | lead  | Self-review (FATAL/MAJOR/MINOR) | `outputs/.drafts/pycheck-feature-roadmap-verification.md` | pending |
| D1  | lead  | Deliver brief + provenance | `outputs/pycheck-feature-roadmap.md`, `outputs/pycheck-feature-roadmap.provenance.md` | pending |

## Verification Log

- No evidence gathered yet (awaiting approval).
- Scale decision recorded before owner assignment. ✅
- Prior-brief context loaded; treated as secondary evidence, not a substitute
  for re-checking anything load-bearing.

## Decision Log

- 2026-09-27: Selected slug `pycheck-feature-roadmap` (topic is "what to add
  next to the shrinking library", anchored to the built wedge E).
- 2026-09-27: Chose **direct search** over 3 researcher subagents, for the
  three reasons in the Scale Decision (anchored local evidence, prior 402
  failure, bounded external evidence).
- 2026-09-27: Output path `outputs/` (non-paper brief), not `papers/`.

## Deliverable

A cited brief that answers: **what should be added to pycheck next, why, in
what order, and what does the coherent "smart, valuable tool" on top of the
existing shrinking core look like?** Ranked, evidence-backed, with explicit
caveats, open questions, and a recommended first build.
