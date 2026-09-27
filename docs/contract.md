# The contract

[← Back to the README](../README.md)

`shrink_rows(frame, fails, *, max_evals=10_000) -> Repro | None`

- **Bugs panic.** An empty frame or `max_evals < 1` raises `ValueError`; a
  `fails` that raises propagates unchanged (never swallowed as "does not fail");
  a `fails` that returns `None` raises `TypeError`.
- **Expected failures are values.** A non-failing input returns `None`; an
  exhausted budget returns a `Repro` with `minimality_proven=False` — still a
  valid repro, just not proven minimal.
- **On success.** `Repro.frame` fails, has ≥1 row, preserves the original row
  order, and when `minimality_proven` is `True`, removing any single row makes
  `fails` return `False`.

Full contract, algorithm, and references:
[`../src/dfshrink/shrink.py`](../src/dfshrink/shrink.py).
