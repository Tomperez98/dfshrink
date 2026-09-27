"""shrink_rows against a dataframely schema.

Requires the ``dataframely`` extra:

    uv sync --extra dataframely

Run it:

    uv run python examples/dataframely_schema.py
"""

from __future__ import annotations

import dataframely as dy
import polars as pl

from dfshrink.ext.dataframely import shrink_rows


class HouseSchema(dy.Schema):
    amount = dy.Int64(nullable=False, min=0)


ledger = pl.DataFrame({"amount": [5, 50, -9, 7, 8]})
repro = shrink_rows(ledger, HouseSchema)
print("dataframely:", repro.frame["amount"].to_list())  # noqa: T201 -> [-9]
