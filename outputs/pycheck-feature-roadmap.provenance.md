# Provenance: What to add to pycheck (feature roadmap)

- **Date:** 2026-09-27
- **Rounds:** 1 (direct search, lead-owned)
- **Sources consulted:** 21 (19 external + 2 local primary: `src/pycheck/shrink.py`, `README.md`; plus the prior brief `outputs/dataframe-contract-gaps.md`)
- **Sources accepted:** 21 — 2 local primary; 4 literature (HDD, Perses, falsify, test-outcome caching, Evaluating Shrinking); 4 dataframely pages; 2 pandera pages; 1 patito; 3 analogue UX (pointblank, minex, Hypothesis); 3 pipeline-attribution (OptDebug, BigSift, BugDoc); 1 prior brief (secondary).
- **Sources rejected:** none (all URLs surfaced content via direct fetch or web search; no dead links encountered).
- **Verification:** PASS WITH NOTES — no FATAL/MAJOR findings. Direct-fetch verified: pandera polars + lazy-validation, dataframely README (raw). Search-returned-content verified: dataframely `FailureInfo` pages, patito, pointblank, minex, Hypothesis, OptDebug/BigSift/BugDoc. Literature DOIs authoritative via Semantic Scholar/OpenAlex. No fresh HTTP-200 sweep of every DOI (recorded, not overclaimed). `falsify` cited secondhand via the prior brief.
- **Plan:** outputs/.plans/pycheck-feature-roadmap.md
- **Research files:**
  - outputs/.drafts/pycheck-feature-roadmap-research-direct.md
  - outputs/.drafts/pycheck-feature-roadmap-draft.md
  - outputs/.drafts/pycheck-feature-roadmap-cited.md
  - outputs/.drafts/pycheck-feature-roadmap-verification.md
