# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release manager edits the `Unreleased` section into the release (see
[RELEASING.md](RELEASING.md)); `mise run changelog` lists the merged commits to
check it against.

## [Unreleased]

## [0.1.0] - Unreleased

The first release. Not yet published to PyPI.

### Added

- `shrink_rows(frame, fails, *, max_evals=10_000)`: delta debugging (`ddmin`)
  over a Polars frame's rows, returning the smallest subset on which `fails`
  is still `True` (`Repro`), or `None` when the frame does not fail.
- Validator adapters: `dfshrink.ext.dataframely`, `dfshrink.ext.pandera`,
  `dfshrink.ext.patito`, and `as_predicate` for a plain `DataFrame -> bool`.
- Failure-aware diagnosis (`diagnose`) that reports the rule and column that
  broke, not just the rows.
- Value and boundary minimization (`minimize_values`, `direction_for_rule`) and
  schema-aware column reduction (`minimize_columns`).
- `Repro` rendering: `to_code()` (round-trippable), `to_markdown()`,
  `as_frame()`, and `str()`.
- `dfshrink.ext.pytest.assert_valid`: fail a test with the minimal repro
  instead of a traceback.

[Unreleased]: https://github.com/Tomperez98/pycheck/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Tomperez98/pycheck/releases/tag/v0.1.0
