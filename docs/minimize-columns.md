# Drop the columns the rule does not need

[← Back to the README](../README.md)

Row shrinking keeps every column; a repro often carries columns the failing rule
never reads. `minimize_columns` removes them while keeping the *same* failure.
Hand it the adapter's explainer, so a drop is accepted only while the validator
still names the same rule and column:

```python
import pandera.polars as pa
from dfshrink import minimize_columns
from dfshrink.ext.pandera import as_failure, diagnose

schema = pa.DataFrameSchema({"amount": pa.Column(int, pa.Check.gt(0))})
df = pl.DataFrame({"amount": [5, -9, 7], "note": ["a", "b", "c"], "debug": [1, 2, 3]})

found = diagnose(df, schema)  # rule 'greater_than(0)' on 'amount'
reduced = minimize_columns(found, as_failure(schema))

reduced.repro.frame.columns  # ['amount'] -- note and debug are gone
reduced.dropped_columns  # ('note', 'debug')
reduced.proven  # True: dropping any kept column changes the reason
```

`minimize_columns` is schema-aware on purpose: a black-box `df -> bool` cannot
tell "still fails for the original reason" from "now fails because a column went
missing." A drop is kept only while the explainer reports the same rule and
column; a drop that merely breaks the frame some other way is rejected. Pass
`columns=True` to `diagnose` to run it in one call:

```python
found = diagnose(df, schema, columns=True)
found.repro.frame.columns  # ['amount']
```

Minimality has two dimensions and both are reported honestly: `reduced.proven`
is the column dimension, and `reduced.repro.minimality_proven` is the row
dimension, re-checked against the preserved reason so a column drop never
inherits a stale flag. The column search gets its own `max_evals` budget. What
can be dropped is the validator's call: dataframely's `filter` returns invalid
rows with only its declared columns, so it drops undeclared columns; pandera also
drops declared-but-unreferenced ones; patito treats superfluous columns as the
failure itself, so it drops none.
