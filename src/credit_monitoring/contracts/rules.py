"""Naming of contract rules, traced back to the ``contract:`` configuration block.

The rule names in the diagnostic are the same keys the team edits in
``configs/project.yaml``, so a rejection points directly at the rule that was broken.
Pandera's ``failure_cases`` frame also carries the offending value of every failing row;
those values are dropped here and only rule, column and count survive.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FailedRule:
    """One broken rule, aggregated over the batch."""

    rule: str
    column: str | None
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "column": self.column, "count": self.count}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if isinstance(result, bool) else False


def classify_failure(row: Any, config: dict[str, Any]) -> tuple[str, str | None]:
    """Return the rule name and the column of one pandera failure case."""
    contract = config.get("contract", {})
    check = row.get("check")
    failure_case = row.get("failure_case")
    column = row.get("column")
    descriptor = str(check) if check is not None else ""

    if descriptor == "column_in_dataframe":
        # Pandera reports the missing column in ``failure_case`` here.
        missing = None if _is_missing(failure_case) else str(failure_case)
        return "missing_column", missing

    column_name = None if _is_missing(column) else str(column)
    failure = str(failure_case) if failure_case is not None else ""

    if failure == "missing_column":
        return "missing_column", column_name
    if descriptor.startswith("field_uniqueness"):
        rule = "require_unique_id" if contract.get("require_unique_id", True) else "unique_id"
        return rule, column_name
    if descriptor.startswith("greater_than"):
        rule = (
            "require_positive_limit_bal"
            if contract.get("require_positive_limit_bal", True)
            else descriptor
        )
        return rule, column_name
    if descriptor.startswith("in_range"):
        return "age_out_of_range", column_name
    if descriptor.startswith("not_nullable"):
        rule = "reject_null_features" if contract.get("reject_null_features", True) else descriptor
        return rule, column_name
    if descriptor.startswith("isin"):
        return "invalid_target", column_name
    if descriptor.startswith("coerce_dtype"):
        return "coerce_dtype", column_name
    if descriptor.startswith("dtype"):
        return "dtype", column_name
    if descriptor and descriptor != "None":
        return descriptor, column_name
    return "invalid_value", column_name
