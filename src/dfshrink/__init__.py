"""dfshrink -- fail-fast data tooling for Polars."""

from __future__ import annotations

from dfshrink.columns import ColumnReduction, minimize_columns
from dfshrink.failure import Diagnosis, Explainer, Failure
from dfshrink.shrink import DEFAULT_MAX_EVALS, FailPredicate, Repro, shrink_rows
from dfshrink.values import Direction, ValueReduction, direction_for_rule, minimize_values

__all__ = [
    "DEFAULT_MAX_EVALS",
    "ColumnReduction",
    "Diagnosis",
    "Direction",
    "Explainer",
    "FailPredicate",
    "Failure",
    "Repro",
    "ValueReduction",
    "direction_for_rule",
    "minimize_columns",
    "minimize_values",
    "shrink_rows",
]
