"""Fail on broken repo-local links in Markdown (COMPAT.md rule 8).

External links are left to the network; links that point at files in this repo
(relative paths, or ``github.com/<owner>/<repo>/blob/main/...`` URLs) must
resolve. A page that moved without a redirect is a red build.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/Tomperez98/pycheck"
ROOT_MARKDOWN = ("README.md", "CHANGELOG.md", "RELEASING.md", "CONTRIBUTING.md")
DOCS = REPO / "docs"
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
BLOB_PREFIXES = (f"{REPO_URL}/blob/main/", f"{REPO_URL}/tree/main/")


def fail(message: str) -> None:
    """Report a check failure and exit non-zero."""
    sys.stderr.write(f"check-links: {message}\n")
    raise SystemExit(1)


def markdown_files() -> list[Path]:
    """Return the Markdown files whose links are checked."""
    roots = [REPO / name for name in ROOT_MARKDOWN]
    files = [path for path in roots if path.is_file()]
    files.extend(sorted(DOCS.glob("*.md")))
    return files


def resolve(base: Path, raw: str) -> Path | None:
    """Resolve a link to a repo path, or ``None`` for external links."""
    href = raw.split("#", 1)[0].strip()
    if not href or href.startswith(("mailto:", "tel:")):
        return None
    if href.startswith(("http://", "https://")):
        for prefix in BLOB_PREFIXES:
            if href.startswith(prefix):
                return REPO / href[len(prefix) :]
        return None
    return (base / href).resolve()


def main() -> None:
    """Check every repo-local Markdown link resolves to an existing file."""
    files = markdown_files()
    if not files:
        fail("no Markdown files found; refusing to report success")

    broken: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            target = resolve(path.parent, raw)
            if target is not None and not target.exists():
                broken.append(f"{path.relative_to(REPO)} -> {raw}")

    if broken:
        for item in broken:
            sys.stderr.write(f"check-links: broken link {item}\n")
        raise SystemExit(1)

    sys.stdout.write(f"check-links: ok ({len(files)} files)\n")


if __name__ == "__main__":
    main()
