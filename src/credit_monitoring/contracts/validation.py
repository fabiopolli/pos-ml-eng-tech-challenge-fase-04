"""Batch validation against the data contract.

``validate_batch`` is the single entry point used by training, by the evaluation stage
and by the future inference path of phase 2. It either returns the validated frame or
raises :class:`ContractViolation`; it never drops rows.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa

from credit_monitoring.contracts.diagnostics import ContractViolation, diagnose
from credit_monitoring.contracts.rules import FailedRule
from credit_monitoring.contracts.schema import build_inference_schema, build_labeled_schema


def validate_batch(
    frame: pd.DataFrame, config: dict[str, Any], *, labeled: bool = True
) -> pd.DataFrame:
    """Validate the whole batch; raise ``ContractViolation`` instead of cleaning it."""
    schema = build_labeled_schema(config) if labeled else build_inference_schema(config)
    try:
        return schema.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as error:
        raise diagnose(error.failure_cases, rejected_rows=len(frame), config=config) from None
    except pa.errors.SchemaError as error:
        raise ContractViolation(
            rejected_rows=len(frame),
            rules=(FailedRule(rule=str(error), column=None, count=len(frame)),),
        ) from None


def validate_file(
    path: str | Path, config: dict[str, Any], *, labeled: bool = True
) -> pd.DataFrame:
    """Read a CSV and validate it against the contract."""
    frame = pd.read_csv(path)
    return validate_batch(frame, config, labeled=labeled)
