# T1 Brief — OSS landscape & feature gaps

You are the **T1** researcher for the deep research run `dataframe-contract-gaps`.
Write your findings to `outputs/.drafts/dataframe-contract-gaps-research-oss.md`.

## Mission

Map the current open-source landscape for Python dataframe validation /
data-contract tooling, with a focus on polars, and identify **explicit,
evidence-backed gaps**. Do NOT propose solutions — gather evidence.

## Scope (cover all, be concrete)

For each of: **polars core**, **dataframely**, **patito**, **pandera**,
**pointblank**, **Great Expectations**, **Soda Core**, **pydantic** (as a
baseline), and any other notable tool you find (**pointblank**, **frictionless**,
**pandera**, **dagster/dbt checks**, **polars `check`/`collect(schema=)`**):

1. **Capabilities:** what validation does it actually support? Distinguish:
   schema/type checks, nullability, ranges/uniqueness, cross-column rules,
   cross-frame/referential integrity, schema inference, error reporting
   quality, data-generation.
2. **Polars support:** native polars backend vs pandas-only vs plugin. Exact
   status.
3. **Static/plan behavior:** does it validate *data*, or can it verify/push
   constraints into a lazy plan *without collecting*? Flag if nothing does.
4. **Streaming:** any support for validating streaming/batched input with state
   (uniqueness across batches, windowed invariants)? Flag if none.
5. **Maintenance & adoption:** latest version + release date (check PyPI),
   GitHub stars / recent commit activity if available, license. Note dead or
   dormant projects.
6. **Known limitations:** quote issues/docs where maintainers say something is
   unsupported or a hard problem.

## Method

- Use PyPI JSON metadata (`https://pypi.org/pypi/<pkg>/json`) for versions and
  summaries. Use web search + fetch for READMEs, docs, GitHub issues.
- Verify versions/dates with a tool; do not rely on memory.
- Prefer primary sources (docs, repo files, issue threads) over blog summaries.
- If a source fails, continue and mark it blocked.

## Output format

`outputs/.drafts/dataframe-contract-gaps-research-oss.md`:

- A **feature matrix table** (rows = libraries, cols = capability dimensions,
  cells = Yes / Partial / No / Unknown with a source link).
- **Per-library notes** with version, maintenance status, source URLs.
- A **"confirmed gaps"** section: list each gap as a claim + the exact evidence
  (URL) that no listed tool solves it, or mark as "unverified".
- A **"surprises / corrections"** section (e.g. a gap I assumed is already
  solved).
- Full **source list** with URLs.

Every factual claim must carry a URL. Mark inferences as inferences.
