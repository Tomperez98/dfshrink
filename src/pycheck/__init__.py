"""pycheck -- fail-fast data tooling for Polars."""

from __future__ import annotations

from pycheck.failure import Diagnosis, Explainer, Failure
from pycheck.shrink import DEFAULT_MAX_EVALS, FailPredicate, Repro, shrink_rows

__all__ = [
    "DEFAULT_MAX_EVALS",
    "Diagnosis",
    "Explainer",
    "FailPredicate",
    "Failure",
    "Repro",
    "shrink_rows",
]
