"""shrink_rows against a patito model.

Requires the ``patito`` extra:

    uv sync --extra patito

Run it:

    uv run python examples/patito_schema.py
"""

from __future__ import annotations

import patito as pt
import polars as pl

from pycheck.ext.patito import shrink_rows


class House(pt.Model):
    amount: int = pt.Field(ge=0)


ledger = pl.DataFrame({"amount": [5, 50, -9, 7, 8]})
repro = shrink_rows(ledger, House)
print("patito:", repro.frame["amount"].to_list())  # noqa: T201 -> [-9]
