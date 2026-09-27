# Provenance: Where Is the Edge in Polars Data Contracts?

- **Date:** 2026-09-27
- **Rounds:** 4 (1 planned subagent round, 3 direct-search rounds after subagent failure)
- **Mode:** DEGRADED — direct lead-owned search. The planned 3-researcher fan-out failed:
  all three children died with provider HTTP 402 (`in_flight_budget_exhausted`; nested
  error: "This request requires more credits, or fewer max_tokens. You requested up to
  393216 tokens, but can only afford 369211"). No child produced an output file.
- **Sources consulted:** ~39 cited sources across polars/validation docs, PyPI, GitHub,
  web search, Semantic Scholar, OpenAlex, and arXiv.
- **Sources accepted:** primary/strong — dataframely docs+repo, polars docs (streaming,
  testing, plugins, LazyFrame), pandera polars docs, Posit survey, PyPI metadata, GitHub
  API metadata, arXiv 2403.03193, arXiv 2607.03889, DOI 10.1109/ACCESS.2022.3146287,
  DOI 10.14778/3229863.3229867, DOI 10.1145/3609026.3609733, minex/CRAN.
- **Sources rejected / downgraded:** Colnade, datalasi, DriftBrake, dframe-trace —
  marketing-style pages from web search with no independent adoption evidence; retained
  but explicitly flagged as weak signals.
- **Verification:** PASS WITH NOTES. All 17 key URLs returned HTTP 200 (2026-09-27);
  both arXiv IDs title-verified. Two MAJOR issues found in self-review and fixed
  (library-count imprecision; streaming-gap overclaim). No independent `verifier` or
  `reviewer` subagent ran (provider 402).
- **Plan:** outputs/.plans/dataframe-contract-gaps.md
- **Research files:**
  - Direct notes: outputs/.drafts/dataframe-contract-gaps-research-direct.md
  - Draft: outputs/.drafts/dataframe-contract-gaps-draft.md
  - Cited: outputs/.drafts/dataframe-contract-gaps-cited.md
  - Self-verification: outputs/.drafts/dataframe-contract-gaps-verification.md
  - Salvaged partial subagent transcripts (unverified leads; not used as evidence):
    session subagent-artifacts for runs 3fa02943, 2ffde60d, f71cfc3d
- **Final:** outputs/dataframe-contract-gaps.md
- **Blocked checks:** independent adversarial review; exhaustive registry audit;
  user-demand research.

## Answer in one line

The "build a validator" idea is saturated; the defensible edge is **tooling around
validation failures** — first **minimal failing-dataframe shrinking** (no Python/polars
incumbent; R has `minex::reduce_rows()`), with **value-constraint verification across a
transformation DAG** as the high-ceiling north star.
