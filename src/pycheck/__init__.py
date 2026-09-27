"""pycheck -- fail-fast data tooling for Polars."""

from __future__ import annotations

from pycheck.failure import Diagnosis, Explainer, Failure
from pycheck.shrink import DEFAULT_MAX_EVALS, FailPredicate, Repro, shrink_rows
from pycheck.values import Direction, ValueReduction, direction_for_rule, minimize_values

__all__ = [
    "DEFAULT_MAX_EVALS",
    "Diagnosis",
    "Direction",
    "Explainer",
    "FailPredicate",
    "Failure",
    "Repro",
    "ValueReduction",
    "direction_for_rule",
    "minimize_values",
    "shrink_rows",
]
