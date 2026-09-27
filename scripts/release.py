"""Build, publish, and verify dfshrink releases (PUBLISH.md).

Every subcommand is safe to run again. ``build`` needs no credentials and runs
on every merge (CI.md rule 8); ``publish`` checks its preconditions before it
touches the registry; ``verify`` installs what users actually get.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
CHANGELOG = REPO / "CHANGELOG.md"
DEFAULT_REPO_SLUG = "Tomperez98/pycheck"
VERSION_RE = re.compile(r'(?m)^version = "[^"]+"$')
SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
USER_AGENT = "dfshrink-release"
SMOKE = (
    "import dfshrink, polars as pl\n"
    "assert dfshrink.__version__ == {version!r}, dfshrink.__version__\n"
    "frame = pl.DataFrame({{'x': [1, -1, 2]}})\n"
    "repro = dfshrink.shrink_rows(frame, lambda d: bool((d['x'] < 0).any()))\n"
    "assert repro is not None and repro.frame.height == 1\n"
    "print('smoke ok', dfshrink.__version__)\n"
)


def say(message: str) -> None:
    """Print a progress line."""
    sys.stdout.write(f"{message}\n")


def fail(message: str) -> None:
    """Report a failed precondition and exit non-zero."""
    sys.stderr.write(f"release: {message}\n")
    raise SystemExit(1)


def run(command: list[str], *, cwd: Path = REPO) -> None:
    """Run a command, inheriting stdout, and fail on a non-zero exit."""
    subprocess.run(command, cwd=cwd, check=True)


def capture(command: list[str], *, cwd: Path = REPO) -> str:
    """Run a command and return its stripped stdout."""
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_metadata() -> dict[str, Any]:
    """Return the ``[project]`` table from ``pyproject.toml``."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    metadata: dict[str, Any] = data["project"]
    return metadata


def version_key(value: str) -> tuple[int, ...]:
    """Parse a ``X.Y.Z`` version into a comparable tuple."""
    match = SEMVER_RE.fullmatch(value)
    if match is None:
        fail(f"version {value!r} is not X.Y.Z; this project ships SemVer only")
    return tuple(int(part) for part in match.groups())


def expected_artifacts(name: str, version: str) -> list[str]:
    """Return the artifact names a release must contain, written by hand."""
    return [f"{name}-{version}.tar.gz", f"{name}-{version}-py3-none-any.whl"]


def artifact_names(directory: Path) -> list[str]:
    """Return the release artifacts in a directory, ignoring scaffolding files."""
    return sorted(
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith((".whl", ".tar.gz"))
    )


def fetch_json(url: str, token: str | None = None) -> tuple[int, Any]:
    """GET JSON, returning ``(status, body)``; a 404 yields ``(404, None)``."""
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, None


def github_token() -> str:
    """Return a GitHub token from the environment, or fail."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        fail("GITHUB_TOKEN is required: publishing runs in CI, against a tested commit")
    return token


def _github(slug: str, path: str) -> tuple[int, Any]:
    """GET an authenticated GitHub API path for ``slug``."""
    return fetch_json(f"https://api.github.com/repos/{slug}{path}", token=github_token())


# --- build ------------------------------------------------------------------


def assert_artifact_contents(path: Path, name: str, version: str) -> None:
    """Check a built artifact identifies itself as the intended release."""
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            metadata_name = next(
                (entry for entry in names if entry.endswith(".dist-info/METADATA")), None
            )
            if metadata_name is None:
                fail(f"{path.name} has no dist-info/METADATA")
            metadata = archive.read(metadata_name).decode("utf-8")
            if f"Name: {name}" not in metadata or f"Version: {version}" not in metadata:
                fail(f"{path.name} does not report {name} {version}")
            if f"{name}/py.typed" not in names:
                fail(f"{path.name} is missing {name}/py.typed")
    else:
        with tarfile.open(path) as archive:
            names = archive.getnames()
            root = f"{name}-{version}"
            if f"{root}/pyproject.toml" not in names:
                fail(f"{path.name} is not an sdist for {name} {version}")


def command_build(args: argparse.Namespace) -> None:
    """Build every artifact once, verify it, and write the release manifest."""
    metadata = project_metadata()
    name = str(metadata["name"])
    version = str(metadata["version"])
    out_dir = Path(args.out_dir).resolve()
    commit = args.commit or capture(["git", "rev-parse", "HEAD"])

    if out_dir.exists():
        for stale in out_dir.iterdir():
            if stale.is_file():
                stale.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    run(["uv", "build", "--out-dir", str(out_dir)])

    expected = expected_artifacts(name, version)
    built = artifact_names(out_dir)
    if built != sorted(expected):
        fail(f"built {built}, expected {sorted(expected)}")

    for artifact in expected:
        assert_artifact_contents(out_dir / artifact, name, version)

    manifest = {
        "name": name,
        "version": version,
        "commit": commit,
        "python_requires": str(metadata.get("requires-python", "")),
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "files": {artifact: sha256(out_dir / artifact) for artifact in expected},
    }
    (out_dir / "release.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    say(f"build: {name} {version} at {commit[:12]} -> {out_dir}")
    for artifact in expected:
        say(f"  {artifact}  {manifest['files'][artifact]}")


def load_manifest(path: str) -> dict[str, Any]:
    """Load and sanity-check a release manifest."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        fail(f"manifest {path} not found; run `scripts/release.py build` first")
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("name", "version", "commit", "files"):
        if key not in manifest:
            fail(f"manifest {path} is missing {key!r}")
    return manifest


# --- publish ----------------------------------------------------------------


def pypi_release(name: str, version: str) -> tuple[int, Any]:
    """Return the PyPI JSON for a version, or ``(404, None)`` if unpublished."""
    return fetch_json(f"https://pypi.org/pypi/{name}/{version}/json")


def published_digests(body: Any) -> dict[str, str]:
    """Map published filename to its sha256 from a PyPI JSON body."""
    return {entry["filename"]: entry["digests"]["sha256"] for entry in body.get("urls", [])}


def assert_version_is_newer(name: str, version: str) -> None:
    """Assert the version goes up and builds on the latest release."""
    status, body = fetch_json(f"https://pypi.org/pypi/{name}/json")
    if status == 404:
        say("publish: first release for this package")
        return
    if status != 200:
        fail(f"PyPI metadata for {name} returned HTTP {status}")
    latest = str(body["info"]["version"])
    if version_key(version) <= version_key(latest):
        fail(f"version {version} is not newer than the published {latest}")
    say(f"publish: {version} builds on the published {latest}")


def assert_commit_is_on_main(commit: str) -> None:
    """Assert the commit is an ancestor of ``main``, and that its CI passed."""
    slug = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG
    status, body = _github(slug, f"/compare/main...{commit}")
    if status != 200:
        fail(f"cannot compare main...{commit} on GitHub (HTTP {status})")
    if body.get("status") not in {"behind", "identical"}:
        fail(f"commit {commit[:12]} is not on main (compare status {body.get('status')})")

    status, body = _github(slug, f"/actions/workflows/ci.yml/runs?head_sha={commit}&per_page=20")
    if status != 200:
        fail(f"cannot read CI results for {commit[:12]} (HTTP {status})")
    runs = body.get("workflow_runs", [])
    if not any(run.get("conclusion") == "success" for run in runs):
        fail(f"CI has no successful run for {commit[:12]}; refusing to publish")


def command_publish(args: argparse.Namespace) -> None:
    """Upload a previously built and tested release, idempotently."""
    manifest = load_manifest(args.manifest)
    name = str(manifest["name"])
    version = str(manifest["version"])
    files: dict[str, str] = manifest["files"]
    dist = Path(args.manifest).resolve().parent

    status, body = pypi_release(name, version)
    if status == 200:
        published = published_digests(body)
        if all(published.get(name_) == digest for name_, digest in files.items()):
            say(f"publish: {name} {version} already published with identical bytes; nothing to do")
            return
        clash = [
            name_
            for name_, digest in files.items()
            if name_ in published and published[name_] != digest
        ]
        if clash:
            fail(f"version {version} already holds different bytes for {clash}; bump the version")
        fail(f"version {version} exists on PyPI but is incomplete; investigate before retrying")
    if status != 404:
        fail(f"PyPI lookup for {name} {version} returned HTTP {status}")

    assert_version_is_newer(name, version)
    assert_commit_is_on_main(str(manifest["commit"]))

    paths = [str(dist / artifact) for artifact in files]
    for path in paths:
        if not Path(path).is_file():
            fail(f"expected artifact {path} is missing")
    run(["uv", "publish", *paths])
    say(f"publish: uploaded {name} {version}")


# --- verify -----------------------------------------------------------------


def local_wheel(dist: Path, name: str, version: str) -> Path:
    """Return the built wheel for this release, or fail."""
    wheel = dist / f"{name}-{version}-py3-none-any.whl"
    if not wheel.is_file():
        fail(f"expected wheel {wheel} not found; run build first")
    return wheel


def command_smoke(args: argparse.Namespace) -> None:
    """Install the built wheel into a clean venv and smoke-test it."""
    manifest = load_manifest(args.manifest)
    name = str(manifest["name"])
    version = str(manifest["version"])
    dist = Path(args.manifest).resolve().parent
    wheel = local_wheel(dist, name, version)

    venv = Path(args.venv_dir).resolve()
    run(["uv", "venv", "--clear", "--python", args.python, str(venv)])
    python = venv / "bin" / "python"
    run(["uv", "pip", "install", "--python", str(python), str(wheel)])
    run([str(python), "-c", SMOKE.format(version=version)])
    say(f"smoke: {wheel.name} installs and passes")


def command_verify(args: argparse.Namespace) -> None:
    """Check from the outside that users can install the release."""
    if args.latest:
        name = str(project_metadata()["name"])
        status, base = fetch_json(f"https://pypi.org/pypi/{name}/json")
        if status != 200:
            fail(f"cannot read {name} metadata from PyPI (HTTP {status})")
        version = str(base["info"]["version"])
        published = published_digests(base)
        for artifact in expected_artifacts(name, version):
            if artifact not in published:
                fail(f"latest release {name} {version} is missing {artifact}")
        say(f"verify: latest on PyPI is {name} {version}")
    else:
        manifest = load_manifest(args.manifest)
        name = str(manifest["name"])
        version = str(manifest["version"])
        files: dict[str, str] = manifest["files"]
        status, body = pypi_release(name, version)
        if status != 200:
            fail(f"{name} {version} is not downloadable from PyPI (HTTP {status})")
        published = published_digests(body)
        for artifact, digest in files.items():
            if artifact not in published:
                fail(f"{artifact} is missing from PyPI")
            if published[artifact] != digest:
                fail(
                    f"{artifact} on PyPI has sha256 {published[artifact]}, "
                    f"built {digest}; users are getting untested bytes"
                )
        if args.expect_latest:
            _, base = fetch_json(f"https://pypi.org/pypi/{name}/json")
            if base is not None and str(base["info"]["version"]) != version:
                fail(f"PyPI 'latest' is {base['info']['version']}, not {version}")

    venv = Path(args.venv_dir).resolve()
    run(["uv", "venv", "--clear", "--python", args.python, str(venv)])
    python = venv / "bin" / "python"
    run(["uv", "pip", "install", "--python", str(python), f"{name}=={version}"])
    run([str(python), "-c", SMOKE.format(version=version)])
    say(f"verify: {name} {version} installs and passes a smoke test from PyPI")


# --- bump and changelog -----------------------------------------------------


def command_bump(args: argparse.Namespace) -> None:
    """Move the version and changelog to a new release in one recorded change."""
    metadata = project_metadata()
    current = str(metadata["version"])
    new = args.version
    if version_key(new) <= version_key(current):
        fail(f"new version {new} must be greater than current {current}")

    text = PYPROJECT.read_text(encoding="utf-8")
    updated, count = VERSION_RE.subn(f'version = "{new}"', text, count=1)
    if count != 1:
        fail("could not find a unique version line in pyproject.toml")
    PYPROJECT.write_text(updated, encoding="utf-8")

    changelog = CHANGELOG.read_text(encoding="utf-8")
    marker = "## [Unreleased]"
    if marker not in changelog:
        fail(f"CHANGELOG.md has no {marker} heading")
    today = datetime.now(tz=UTC).date().isoformat()
    changelog = changelog.replace(marker, f"{marker}\n\n## [{new}] - {today}", 1)
    CHANGELOG.write_text(changelog, encoding="utf-8")

    say(f"bump: {current} -> {new}")
    say("next: review the diff, then commit it and tag the merged commit:")
    say(f'  git commit -am "release: {new}"')
    say("  git push origin HEAD:main")
    say(f"  git tag -a v{new} -m v{new} && git push origin v{new}")


def last_tag() -> str | None:
    """Return the most recent ``vX.Y.Z`` tag, or ``None`` before the first release."""
    try:
        return capture(["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"])
    except subprocess.CalledProcessError:
        return None


def command_changelog(args: argparse.Namespace) -> None:
    """List merged commits since the last tag, for the release manager to edit."""
    tag = last_tag()
    if tag is None:
        commits = capture(["git", "log", "--no-merges", "--format=- %s (%h)"])
        say("no release tag yet; changes since the start of history:")
    else:
        commits = capture(["git", "log", "--no-merges", "--format=- %s (%h)", f"{tag}..HEAD"])
        say(f"changes since {tag}:")
    say(commits or "- (nothing yet)")


# --- entrypoint -------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Return the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build once, verify, and write a manifest")
    build.add_argument("--out-dir", default="dist")
    build.add_argument("--commit", default=None)
    build.set_defaults(func=command_build)

    publish = subparsers.add_parser("publish", help="upload a built release")
    publish.add_argument("--manifest", default="dist/release.json")
    publish.set_defaults(func=command_publish)

    verify = subparsers.add_parser("verify", help="install and smoke-test from PyPI")
    verify.add_argument("--manifest", default="dist/release.json")
    verify.add_argument("--python", default="3.12")
    verify.add_argument("--venv-dir", default=".smoke")
    verify.add_argument("--expect-latest", action="store_true")
    verify.add_argument(
        "--latest",
        action="store_true",
        help="verify the newest published release instead of a local manifest",
    )
    verify.set_defaults(func=command_verify)

    smoke = subparsers.add_parser("smoke", help="install the built wheel and smoke-test it")
    smoke.add_argument("--manifest", default="dist/release.json")
    smoke.add_argument("--python", default="3.12")
    smoke.add_argument("--venv-dir", default=".smoke")
    smoke.set_defaults(func=command_smoke)

    bump = subparsers.add_parser("bump", help="bump the version and changelog")
    bump.add_argument("version")
    bump.set_defaults(func=command_bump)

    changelog = subparsers.add_parser("changelog", help="list changes since the last tag")
    changelog.set_defaults(func=command_changelog)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Dispatch a release subcommand."""
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
