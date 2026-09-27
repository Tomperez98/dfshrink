# Catch it in CI: fail with a repro, not a traceback

[← Back to the README](../README.md)

`dfshrink.ext.pytest.assert_valid` is the CI-shaped replacement for
`assert schema.is_valid(df)`. Point it at the adapter's `diagnose` and it either
returns silently or fails the test with the rule/column and the minimal repro:

```python
from dfshrink.ext.dataframely import diagnose
from dfshrink.ext.pytest import assert_valid


def test_house_schema(df):
    assert_valid(df, HouseSchema, diagnose=diagnose)
```

A failed job now prints the one row and the rule that broke, so the fix and the
regression test both start from the failure. It imports no validator library and
touches no global state, so it works the same inside a fixture. Add
`columns=True` to also strip the columns the failing rule does not read.
