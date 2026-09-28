# Releasing dfshrink

The process is scripted and re-runnable. The only manual parts are the two
decisions: **which commit**, and **go**.

The checklist is written down so a release is runnable by anyone — including
future-you or a new maintainer — without asking the author. The only gate is
the deliberate approve click in the `pypi` environment (step 5).

## One-time setup (do once, before the first release)

1. **PyPI trusted publisher.** On PyPI, add a pending publisher for project
   `dfshrink`: owner `Tomperez98`, repository `dfshrink`, workflow `release.yml`,
   environment `pypi`. No API token is stored anywhere.
2. **Protected environment.** In GitHub → Settings → Environments, create
   `pypi` with approval required, and restrict its deployment branches and tags
   to tags matching `v*`. Only the `publish` job uses it.
3. **Default permissions.** In GitHub → Settings → Actions → General, set the
   default `GITHUB_TOKEN` to read-only; each workflow asks for what it needs.
4. **Protect `main`.** Require the three `ci.yml` checks (`static`, `test`,
   `package`) and "Require branches to be up to date before merging", so a
   branch is tested against the main it will land on. Enable the merge queue so
   a batch is tested after merging, not just before. Nobody merges past a red
   check.

## Routine release

Run these in order. Each step names the exact command.

1. **Confirm main is green.** `main` must be passing `mise run ci`, and the
   post-merge monitor (`monitor.yml`) must be green for the candidate commit.
   If a check is red, fix it before releasing — never rush a change in.

2. **Prepare the version in a pull request.** The changelog's top versioned
   entry is the source of truth. Derive the next version from it and run:

   ```bash
   mise run bump            # patch + 1 from the changelog; edits CHANGELOG.md only.
                            # pyproject.toml stays the 0.0.0 placeholder.
   mise run changelog       # lists merged commits since the last tag; edit
                            # the [Unreleased] section from that list
   mise run ci              # the same gate CI will run
   ```

   For a minor or major bump, name the component instead: `uv run python
   scripts/release.py bump --kind minor` (or `--kind major`). Commit, push a
   branch, open a PR, and get it reviewed and merged. `pyproject.toml` always
   pins the `0.0.0` placeholder; the release build stamps the real version into
   a temporary copy, so a dev build can never look like a release.

3. **Freeze the tested commit.** Release exactly the commit `main` points at,
   never the local checkout. Tag the *remote* SHA:

   ```bash
   git fetch origin main
   sha="$(git rev-parse origin/main)"
   git tag -a v0.2.0 "$sha" -m "v0.2.0"
   git push origin v0.2.0
   ```

   Pushing the tag starts `release.yml`. If the tag does not point at a commit
   that passed CI on `main`, the publish job's preconditions fail.

4. **Confirm the candidate is still green.** `matrix.yml` runs the Python
   matrix for the commit and `monitor.yml` re-checks the published release on a
   schedule. Confirm the matrix is green for the tagged SHA before approving.
   If it is not, delete the tag and skip this release.

5. **Approve and publish.** The `publish` job waits for approval in the `pypi`
   environment. Approve it — that click is the "go" decision. The job re-checks
   every precondition, then uploads the artifacts built in step 3 — it never
   rebuilds.

6. **Verify what shipped.** The `verify` job downloads from PyPI, compares
   checksums against the built manifest, installs the wheel and sdist into
   clean virtualenvs on every supported Python version, and runs a smoke test.
   Confirm it passed and that `latest` on PyPI is this version.

7. **Announce it.** After `verify` passes, the `release` job posts the
   versioned `CHANGELOG.md` section as the GitHub release notes, so the tag
   page links a real changelog instead of an empty one. No manual step; re-run
   the workflow to refresh the notes.

## If something goes wrong

Versions only go up. A published version is never overwritten, re-tagged, or
re-published.

- **Build failed (nothing published).** Fix the cause on `main`, then move the
  tag to the new commit and push it again:
  `git push --delete origin v0.2.0`, re-tag, re-push. No version is burned.
- **Publish failed partway (some artifacts uploaded).** The publish step first
  checks PyPI. Re-run the failed workflow (or download the `dist` artifact from
  the failed run and run `mise run release:publish`). It uploads only what is
  missing and fails if the version holds different bytes.
- **Verify failed after a successful upload.** Users may be getting untested
  bytes. Delete the uploaded files on PyPI if the release is dangerous to keep
  running, yank the version, then fix forward with a new patch version. Do not
  re-upload the same version.
- **A bad release is already out.** Fix forward: a new patch version through the
  same process. If it is dangerous to keep running, yank it on PyPI and say so
  on the release page, with migration steps.
- **Emergency fix that cannot ship normally** (upgrading to the fix is itself
  broken): yank the broken version, then follow the routine release for the
  patch. Do not hand-upload artifacts.

## What guards each release

- `release.yml` builds without credentials, then publishes the same bytes from a
  protected job, verifies from the outside, then posts the changelog section as
  the GitHub release notes.
- The publish preconditions are: the version is new and newer than the latest,
  the commit is on `main`, CI passed for that commit, and the built artifact set
  matches the expected list. A broken precondition stops the release.
- `monitor.yml` re-runs the verification on a schedule, so a package that
  disappears or a broken download surfaces without a user reporting it.
