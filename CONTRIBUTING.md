# Contributing

Thanks for helping. The one rule this project optimizes for: **keep `main`
releasable.** Any commit on `main` could be released, so a change is done when
it is green and reviewed, not when it is pushed.

## Set up

```bash
mise install          # installs the pinned Python and uv
mise run setup        # installs every dependency (uv sync --all-extras --dev)
```

## Before you open a pull request

```bash
mise run ci           # the same gate CI runs, in cost order
```

`mise run ci` runs formatting, lint, the type checker, repo-hygiene checks, the
unit tests, every example, a release build, and a clean-install smoke test. Run
one tier while iterating (`mise run test`, `mise run lint`, `mise run type`).
Every diagnostic is an error; a warning is a bug.

## What CI checks

- `ruff format --check` and `ruff check` at `select = ["ALL"]`.
- `ty check` with every diagnostic treated as an error.
- `pytest` (a failing test must reproduce; randomness prints its seed).
- Repo hygiene: no source files outside the declared package, no broken
  repo-local Markdown links.
- The release path in dry-run: build the artifacts and install the wheel into a
  clean environment.

## Pull requests

- Keep the change small and the tests with it. A bug fix lands with a test that
  fails before and passes after.
- Do not edit generated artifacts by hand; regenerate them.
- Don't merge past a red check, and don't retry a flaky test until it passes —
  fix it or quarantine it with an owner.
- New behavior that users would notice gets a `CHANGELOG.md` entry under
  `Unreleased`.

## Releases

Releases are run from `main` and documented in [RELEASING.md](RELEASING.md).
You do not need release credentials to build: `mise run build` runs anywhere.
