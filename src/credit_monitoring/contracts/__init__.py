"""Data contract (Pandera) for the credit scoring pipeline.

The contract is the gate between data and model. It is applied *before* any estimator
is fitted and *before* any batch is inferred, and it rejects the whole batch when a
rule is broken: an operational batch is never silently cleaned and scored.

Two schemas share the same feature definition:

- ``labeled``: the target column is mandatory and must be binary;
- ``inference``: the same columns without the target, for scoring new batches.

The rules are read from the ``contract:`` block of ``configs/project.yaml`` so the
configuration stays the single source of truth.
"""

from credit_monitoring.contracts.diagnostics import ContractViolation, diagnose
from credit_monitoring.contracts.rules import FailedRule
from credit_monitoring.contracts.schema import (
    CONTRACT_VERSION,
    build_inference_schema,
    build_labeled_schema,
    expected_columns,
)
from credit_monitoring.contracts.validation import validate_batch, validate_file

__all__ = [
    "CONTRACT_VERSION",
    "ContractViolation",
    "FailedRule",
    "build_inference_schema",
    "build_labeled_schema",
    "diagnose",
    "expected_columns",
    "validate_batch",
    "validate_file",
]
