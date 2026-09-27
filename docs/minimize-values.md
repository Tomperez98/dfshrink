# Move the value to the boundary, not just the row

[← Back to the README](../README.md)

Shrinking drops rows; it can't say *how far* past the line a cell is. Under a
`min=0` rule the failing row might be `amount=-9`, but the interesting repro is
the last value that still fails:

```python
from dfshrink import minimize_values
from dfshrink.ext.dataframely import as_predicate, diagnose

found = diagnose(df, HouseSchema)  # repro + why (rule 'amount|min')
reduced = minimize_values(found, as_predicate(HouseSchema))

reduced.repro.frame  # amount == -1 -- the boundary, not -9
reduced.proven  # True: -1 is the failing value next to passing
reduced.column  # 'amount'
reduced.direction  # 'increase'
```

`minimize_values` reads the column from the diagnosis and the direction from the
rule name (`min`/`greater` → increase, `max`/`less` → decrease). Pass a bare
`Repro` with `column=` and `direction=` instead. It assumes the predicate is
monotone *along that column*; when no passing value is found, or the budget runs
out, the cell is left untouched and `proven` is `False` — the step never guesses
a boundary it can't show. Only integer and `Float64` columns are supported.
