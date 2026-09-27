"""Fail when source files drift outside the declared package (COMPAT.md rule 8).

A repo that renames its package can leave the old tree behind, unreferenced and
untested. This check makes that state a red build: ``src/`` holds exactly one
directory, it is the project's import package, and every Python file under
``src/`` lives inside it.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"


def fail(message: str) -> None:
    """Report a check failure and exit non-zero."""
    sys.stderr.write(f"check-orphans: {message}\n")
    raise SystemExit(1)


def expected_package() -> str:
    """Return the import package name derived from the project name."""
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    name: str = data["project"]["name"]
    return name.replace("-", "_")


def main() -> None:
    """Check ``src/`` for orphan packages and files."""
    expected = expected_package()
    package = SRC / expected
    if not package.is_dir():
        fail(f"src/{expected}/ does not exist; expected exactly one package directory")

    siblings = sorted(
        child.name for child in SRC.iterdir() if child.is_dir() and child.name != "__pycache__"
    )
    unexpected = [name for name in siblings if name != expected]
    if unexpected:
        fail(f"src/ contains package directories other than {expected!r}: {unexpected}")

    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        top = path.relative_to(SRC).parts[0]
        if top != expected:
            fail(f"orphan source file outside src/{expected}/: {path.relative_to(REPO)}")

    sys.stdout.write(f"check-orphans: ok (only src/{expected}/)\n")


if __name__ == "__main__":
    main()
