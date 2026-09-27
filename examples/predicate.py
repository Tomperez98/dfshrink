"""shrink_rows with a plain ``DataFrame -> bool`` predicate.

This is the core seam: no validation library, only polars.  Run it:

    uv run python examples/predicate.py
"""

from __future__ import annotations

import polars as pl

from dfshrink import shrink_rows


def has_negative(df: pl.DataFrame) -> bool:
    return bool((df["x"] < 0).any())


# --- 1. A frame that fails: shrinks to the minimal failing rows --------------

repro = shrink_rows(pl.DataFrame({"x": [10, -1, 20, -2, 30, 40]}), has_negative)

# --- 2. A frame that does not fail -> None, not a crash ----------------------

result = shrink_rows(pl.DataFrame({"x": [1, 2, 3]}), has_negative)
