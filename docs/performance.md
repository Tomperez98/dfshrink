# Performance: ~log₂(n) predicate calls

[← Back to the README](../README.md)

The only cost that scales with your data is your predicate. `ddmin` narrows by
chunks instead of removing one row at a time (which is `O(n²)` calls), so a bad
row is isolated in ~log₂(n) calls:

| Frame | Bad rows | Result | Predicate calls |
|---|---|---|---|
| 20,000 rows | 1 | 1 row | 16–29 |
| 6 rows | 1 | 1 row | 4 |

Call counts depend on where the bad rows sit; the range is measured. Candidates
are selected with `DataFrame.slice`, so copying the frame is not the cost: with a
cheap predicate, 20,000 rows shrink to one in ~0.25 ms. With an expensive
predicate the ~log₂(n) calls dominate — cap them with `max_evals` (default
10,000).

That ~log₂(n) figure is the common case: a few bad rows among many. The opposite
case is when the failure needs *most* of the frame — a sum over nearly every row.
Then every proper subset passes, `ddmin` has nothing to remove, and the budget is
what stops the search: on a 40,000-row frame it spends the full 10,000 calls in
~0.6 s before giving up. The result is still a valid repro (the frame itself,
with `minimality_proven=False`) — no smaller subset reproduces the failure. Lower
`max_evals` trades repro quality for a hard time bound.
