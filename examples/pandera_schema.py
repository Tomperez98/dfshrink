"""shrink_rows against a pandera schema.

Requires the ``pandera`` extra:

    uv sync --extra pandera

Run it:

    uv run python examples/pandera_schema.py
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from dfshrink.ext.pandera import shrink_rows


class Accounts(pa.DataFrameModel):
    amount: pa.typing.Series[int] = pa.Field(gt=0)


book = pl.DataFrame({"amount": [100, 200, -50, 300]})
repro = shrink_rows(book, Accounts)
