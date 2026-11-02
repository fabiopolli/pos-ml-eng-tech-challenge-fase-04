"""Structured diagnostics for contract failures.

A contract failure must be actionable without exposing client records: the diagnostic
reports the rule, the column and how many rows failed, never the values themselves.
Pandera's raw ``failure_cases`` frame carries the offending value of every failing row,
so it is aggregated here and the values are dropped.
"""

from __future__ import annotations

from typing import Any

from credit_monitoring.contracts.rules import FailedRule, classify_failure


class ContractViolation(Exception):
    """Raised when a batch does not satisfy the contract.

    ``rules`` lists every broken rule; ``rejected_rows`` is the size of the batch that
    was rejected as a whole (the batch is counted once, even when several rules fail).
    """

    def __init__(self, rejected_rows: int, rules: tuple[FailedRule, ...] = ()) -> None:
        self.rejected_rows = rejected_rows
        self.rules = tuple(rules)
        super().__init__(self._message())

    @property
    def failed_rules(self) -> tuple[str, ...]:
        return tuple(rule.rule for rule in self.rules)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejected_rows": self.rejected_rows,
            "failed_rules": [rule.to_dict() for rule in self.rules],
        }

    def _message(self) -> str:
        details = "; ".join(
            f"{rule.rule}[{rule.column or 'batch'}]={rule.count}" for rule in self.rules
        )
        return f"Contract violation: {self.rejected_rows} rows rejected ({details})"


def diagnose(
    failure_cases: Any, *, rejected_rows: int, config: dict[str, Any]
) -> ContractViolation:
    """Aggregate pandera failure cases into a :class:`ContractViolation`.

    ``failure_cases`` is the frame pandera exposes on ``SchemaErrors``. Only rule, column
    and count survive: the offending values are never copied into the diagnostic.
    """
    if failure_cases is None or len(failure_cases) == 0:
        return ContractViolation(rejected_rows=rejected_rows, rules=())

    counts: dict[tuple[str, str | None], int] = {}
    for _, row in failure_cases.iterrows():
        rule, column_name = classify_failure(row, config)
        key = (rule, column_name)
        counts[key] = counts.get(key, 0) + int(row.get("failure_count", 1) or 1)

    rules = tuple(
        FailedRule(rule=rule, column=column, count=count)
        for (rule, column), count in sorted(counts.items())
    )
    return ContractViolation(rejected_rows=rejected_rows, rules=rules)
