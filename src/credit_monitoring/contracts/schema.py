"""Pandera schemas for the labeled (training) and inference batches.

The rules come from the ``contract:`` block of ``configs/project.yaml``:

- ``require_unique_id``: client identifiers must not repeat inside the batch;
- ``require_positive_limit_bal``: ``LIMIT_BAL`` must be strictly positive;
- ``age_min`` / ``age_max``: ``AGE`` must be inside the inclusive range;
- ``reject_null_features``: mandatory features must not carry null values.

Deliberately **not** enforced: negative bill amounts and the undocumented payment codes
(``EDUCATION`` 0/5/6, ``MARRIAGE`` 0, ``PAY_*`` -2/0). Those are documented facts of the
source data, not defects; the contract reports them instead of recoding them.
"""

from typing import Any

import pandera.pandas as pa

from credit_monitoring.config import canonical_columns, feature_columns

CONTRACT_VERSION = "1.0.0"
TARGET_VALUES = [0, 1]


def _numeric_column(checks: list[pa.Check] | None = None, *, nullable: bool = False) -> pa.Column:
    return pa.Column(
        float,
        checks=checks or [],
        nullable=nullable,
        coerce=True,
        required=True,
    )


def build_labeled_schema(config: dict[str, Any]) -> pa.DataFrameSchema:
    """Schema for a batch that carries the binary target."""
    schema = build_inference_schema(config)
    columns = dict(schema.columns)
    target = config["dataset"]["canonical_target"]
    columns[target] = pa.Column(
        float,
        checks=[pa.Check.isin(TARGET_VALUES)],
        nullable=False,
        coerce=True,
        required=True,
    )
    return pa.DataFrameSchema(
        columns=columns,
        strict=False,
        coerce=None,
        name=f"credit_monitoring_labeled_v{CONTRACT_VERSION}",
    )


def build_inference_schema(config: dict[str, Any]) -> pa.DataFrameSchema:
    """Schema for a batch without the target, used at inference time."""
    dataset = config["dataset"]
    contract = config["contract"]
    id_column = dataset["id_column"]

    columns: dict[str, pa.Column] = {}

    id_checks: list[pa.Check] = []
    columns[id_column] = pa.Column(
        int,
        checks=id_checks,
        nullable=False,
        unique=bool(contract.get("require_unique_id", True)),
        coerce=True,
        required=True,
    )

    financial = feature_columns(config)
    governance = list(dataset["governance_features"])
    for column in financial:
        checks: list[pa.Check] = []
        if column == "LIMIT_BAL" and contract.get("require_positive_limit_bal", True):
            checks.append(pa.Check.gt(0))
        nullable = not contract.get("reject_null_features", True)
        columns[column] = _numeric_column(checks, nullable=nullable)

    # Governance attributes are validated for presence and type, never for domain.
    for column in governance:
        if column == "AGE":
            columns[column] = _numeric_column(
                [pa.Check.in_range(int(contract["age_min"]), int(contract["age_max"]))]
            )
        else:
            columns[column] = _numeric_column()

    return pa.DataFrameSchema(
        columns=columns,
        strict=False,
        coerce=None,
        name=f"credit_monitoring_inference_v{CONTRACT_VERSION}",
    )


def expected_columns(config: dict[str, Any], *, labeled: bool) -> list[str]:
    """Columns the contract expects to be present in the batch."""
    columns = canonical_columns(config)
    if not labeled:
        columns = [column for column in columns if column != config["dataset"]["canonical_target"]]
    return columns


__all__ = [
    "CONTRACT_VERSION",
    "TARGET_VALUES",
    "build_inference_schema",
    "build_labeled_schema",
    "expected_columns",
]
