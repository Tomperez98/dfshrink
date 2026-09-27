# Verification — dataframe-contract-gaps

**Pass type:** self-review (direct-search/degraded mode; the `reviewer` subagent was not
run because the subagent path failed on provider credit ceilings — see plan).
**Artifact reviewed:** `outputs/.drafts/dataframe-contract-gaps-cited.md`
**Date:** 2026-09-27

## Checks performed

1. **URL liveness** — 17 key URLs checked with `curl -sL` (HTTP status) on
   2026-09-27; all returned **200**. (Posit survey, dataframely lazy-validation and
   data-generation, polars streaming/testing/parametric/plugins, pandera polars,
   datalasi, Colnade, typedframes, dataframely GitHub, minex reduce_rows, shrinkplz,
   Union.ai Narwhals, tech.quantco.com.)
2. **Identifier verification** — arXiv IDs checked against `arxiv.org/abs/` pages:
   - `2403.03193` → "VeriEQL: Bounded Equivalence Verification for Complex SQL Queries
     with Integrity Constraints" ✅ title matches.
   - `2607.03889` → "Inferring the Shape of Data Frames in R Programs using Abstract
     Interpretation" ✅ title matches (source [40]).
3. **Version/metadata verification** — versions (polars 1.44.2, dataframely 3.1.2,
   patito 0.8.6, pandera 0.33.1, pointblank 0.27.0, datalasi 0.3.0) via PyPI JSON;
   star counts / last-push via GitHub REST API.
4. **Claim-to-source mapping** — every critical claim in the cited draft carries an
   inline numeric citation; no invented benchmarks, tables, or figures.

## Findings

### FATAL
None.

### MAJOR (fixed)
1. **Imprecise count:** the summary said "at least six validation libraries" while the
   enumeration mixed five validators with two static-typing projects. **Fixed** to
   "at least five polars validation libraries" in `-cited.md`.
2. **Streaming-gap overclaim risk:** "no library for referential integrity" could read
   as ignoring dataframely *collections* (which do batch referential integrity).
   **Fixed** with an explicit clarification that the gap is the cross-batch/streaming
   guarantee, not batch referential integrity.

### MINOR (noted, accepted)
- Star counts mix two dates: Posit survey (mid-2025) for Pandera/patito/pointblank/
  Validoopsie, and GitHub API (2026-09) for dataframely/patito/Validoopsie. Pandera's
  "≈3.8k" is a mid-2025 figure and may be stale.
- Weak-source competitors (Colnade, datalasi, DriftBrake) are flagged in caveats;
  retention is acceptable because they are load-bearing only for the "crowded/absorbed"
  verdicts, which are corroborated by stronger sources (Posit survey; typedframes;
  frameright; pandera-mypy).
- Source [34] uses a mirror URL (`webkkk.net`) for a GitHub README; flagged, not
  load-bearing.

### Coverage gaps (blocked)
- The `verifier`/`reviewer` subagent passes did not run (provider 402). Independent
  adversarial review is therefore **not** present.
- No exhaustive registry audit; "no tool found" claims (wedges C/D/E) are
  search-based, not provably exhaustive.
- No user-demand research.

## Verdict

**PASS WITH NOTES.** The two MAJOR findings were corrected in the cited artifact. The
absence of an independent reviewer and the search-based nature of the "open gap"
claims are the principal residual risks; both are disclosed in the brief's caveats.
