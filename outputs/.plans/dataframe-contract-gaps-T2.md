# T2 Brief — Research, standards & industrial practice

You are the **T2** researcher for the deep research run `dataframe-contract-gaps`.
Write your findings to `outputs/.drafts/dataframe-contract-gaps-research-lit.md`.

## Mission

Survey the academic literature, standards, and industrial engineering practice
relevant to Python dataframe data contracts, so we can tell whether the
candidate gaps are genuinely unsolved or already have known solutions worth
borrowing.

## Candidate problem areas to investigate

1. **Data contracts & standards:** Open Data Contract Standard (ODCS /
   Bitol), data contract manifests, schema registries (Avro/Protobuf/JSON
   Schema evolution semantics). What is standardized, what is not?
2. **Static verification / type systems for dataframes:** work on typed
   dataframes, type inference for dataframe pipelines, constraint verification,
   symbolic execution / abstract interpretation of data transformations.
   (Look for systems like "TypeScript-for-dataframes", dataframe type checkers,
   query-plan verification.)
3. **Constraint pushdown / optimizer integration:** literature on pushing
   validation predicates into query plans, zero-copy/plan-level validation,
   sampling-based approximate validation.
4. **Property-based testing & shrinking for tabular data:** Hypothesis,
   `hypothesis-jsonschema`, data generators, minimal counterexample / delta
   debugging. Is tabular/FK-aware shrinking solved?
5. **ML data validation prior art:** TFX Data Validation / TFDV, Deequ,
   Amazon Deequ constraint suggestion, Great Expectations lineage. What did
   these solve and where did they fall short?
6. **Streaming / stateful data validation:** anomaly detection over streams,
   sketch-based uniqueness, windowed constraints, online validation.

## Method

- Use `feynman_science_database_search` (Semantic Scholar default citation
  sort; OpenAlex for cross-discipline; arXiv only for known IDs) and web search.
- Prefer seminal + recent papers; capture **titles, authors, year, venue,
  identifiers (DOI/arXiv/OpenAlex/S2), citation counts where available, and
  URLs**.
- For standards, cite the official spec pages.
- Read abstracts; only fetch full text for the few works our conclusion hinges
  on.
- If PDF parsing fails, continue from metadata/abstracts and mark blocked.

## Output format

`outputs/.drafts/dataframe-contract-gaps-research-lit.md`:

- **Per-area synthesis** (1 short section each), each claim linked to a source.
- A **prior-art table**: system/paper | problem solved | approach | limitation |
  identifier | URL.
- An **"ideas worth stealing"** section: concrete techniques applicable to a
  Python/polars tool.
- A **"still open"** section: problems the literature explicitly leaves open.
- Full **source list** with identifiers and URLs.

Never invent papers, identifiers, or numbers. If uncertain, say so.
