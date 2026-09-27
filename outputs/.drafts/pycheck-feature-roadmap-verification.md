# Verification — pycheck-feature-roadmap

Date: 2026-09-27 · Self-review (direct-search mode: no verifier/reviewer subagents)

## Checks performed

1. **Claim→source mapping.** Every substantive claim, number, and example in the
   cited draft maps to a source in the Sources section. Walked the draft
   top-to-bottom: no orphaned claims found.
2. **No invented numbers/figures/tables.** The draft introduces no benchmark
   figures, charts, or tables beyond the ~log₂(n) figure, which is quoted from
   pycheck's own README [1][2]. The `{'amount|min_exclusive': 1}` example is
   quoted verbatim from dataframely's docs (search-returned content) [9].
3. **Validator-metadata accuracy.** Cross-checked the three central API claims
   against primary docs: dataframely `FailureInfo.counts/cooccurrence_counts/
   invalid` [6][7][8]; pandera `SchemaErrors.message/.failure_cases/.data`
   [10][11] (direct fetch); patito per-column error detail [12]. All match.
4. **Attribution prior art.** OptDebug/BigSift/BugDoc characterizations match
   their abstracts/snippets [16][17][18].
5. **Inference labeling.** The one material inference (cost/benefit of the
   failure-aware adapter) is explicitly flagged in Q3.

## Findings

- **FATAL:** none.
- **MAJOR:** none.
- **MINOR (accepted):**
  - `falsify` [19] is cited secondhand via the prior brief [21], not re-verified
    against the primary paper. It is a supporting citation, not load-bearing.
  - "No Python/Polars tool reduces columns" is a search-based negative claim,
    not an exhaustive audit; already flagged as a caveat in the draft.
  - "PBT shrinkers minimize values" bundles Hypothesis/falsify/"Evaluating
    Shrinking" loosely; the papers target *shrink quality* and *internal
    shrinking*, not tabular value minimization specifically. Noted, not fixed
    (the framing is qualified as "analogue").
  - The prior brief's open demand-side question (is there real user demand?)
    remains unanswered; carried forward honestly as Open Question 4.

## Verification status

PASS WITH NOTES — direct-fetch verified: pandera [10][11], dataframely README
(raw). Search-returned-content verified: dataframely FailureInfo [6][7][8][9],
patito [12], pointblank [13], minex [14], Hypothesis [15], OptDebug/BigSift/
BugDoc [16][17][18]. Literature DOIs [3][4][5][20] authoritative via Semantic
Scholar/OpenAlex. No fresh HTTP-200 sweep was run against every DOI; that gap is
recorded here rather than overclaimed.
