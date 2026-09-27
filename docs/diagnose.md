# Get the reason, not just the rows: `diagnose`

[← Back to the README](../README.md)

`shrink_rows` answers *which rows*. `diagnose` also answers *why* — the rule and
column the validator flagged — as a ticket-ready report:

```python
from dfshrink.ext.dataframely import diagnose

found = diagnose(df, HouseSchema)
print(found.to_markdown())
```

```text
Validation failed: column 'amount' fails rule 'amount|min'.

Minimal repro:

| amount (Int64) |
| --- |
| -9 |
```

`diagnose` returns `None` when the frame passes, else a `dfshrink.Diagnosis`
whose `repro` is the same minimal repro `shrink_rows` would produce, and whose
`failure` carries the rule, column, and (when the validator exposes them) the
invalid rows. When the validator reports the invalid rows (dataframely, pandera),
shrinking starts there instead of over the whole frame; when it doesn't (patito),
`diagnose` falls back to black-box shrinking and still reports the failing
column.
