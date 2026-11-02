"""Optional financial ratio features for the credit scoring models.

The transformer is **optional**: it is only used by the finalists of the
optimization campaign (plan 1.6, section 4.3) and never by the published
baseline. It is a scikit-learn transformer, so it lives inside the ``Pipeline``
and is fitted inside every cross-validation fold: it holds no fitted state and
never sees the target.

The three ratios are pre-defined by the plan:

- ``bill_amt1_over_limit_bal``   -> ``BILL_AMT1 / LIMIT_BAL``
- ``pay_amt1_over_limit_bal``    -> ``PAY_AMT1 / LIMIT_BAL``
- ``pay_amt1_over_abs_bill_amt1`` -> ``PAY_AMT1 / max(abs(BILL_AMT1), 1.0)``

Properties that the plan requires and that the tests check:

- the formulas preserve negative invoices and zero payments (a zero payment
  gives a zero ratio, never a division by zero);
- the third ratio uses a minimum denominator of **1 NT$**, so a zero invoice
  cannot produce an infinite value;
- the output is always finite;
- the external contract keeps the 19 financial inputs: the ratios are *internal*
  features, derived inside the pipeline, and no CSV is modified.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

RATIO_FEATURE_NAMES = (
    "bill_amt1_over_limit_bal",
    "pay_amt1_over_limit_bal",
    "pay_amt1_over_abs_bill_amt1",
)

REQUIRED_COLUMNS = ("LIMIT_BAL", "BILL_AMT1", "PAY_AMT1")


class FinancialRatioTransformer(BaseEstimator, TransformerMixin):
    """Append three financial ratios derived from the 19 financial inputs.

    Parameters
    ----------
    min_denominator:
        Lower bound applied to the denominators, in NT$. It protects the ratios
        against a non-positive limit or a zero invoice. On contract-valid data
        (``LIMIT_BAL > 0``) the limit denominator is never triggered.
    """

    def __init__(self, min_denominator: float = 1.0) -> None:
        self.min_denominator = min_denominator

    def fit(self, X: pd.DataFrame, y: Any = None) -> "FinancialRatioTransformer":
        """Accept the batch and record the input columns; nothing is learned."""
        self._check_columns(X)
        self.feature_names_in_ = np.asarray(list(X.columns), dtype=object)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Return the input columns followed by the three ratios."""
        self._check_columns(X)
        frame = X.copy()
        limit = frame["LIMIT_BAL"].astype(float)
        bill = frame["BILL_AMT1"].astype(float)
        payment = frame["PAY_AMT1"].astype(float)

        minimum = float(self.min_denominator)
        limit_denominator = limit.where(limit > 0, minimum)
        bill_denominator = bill.abs().clip(lower=minimum)

        frame["bill_amt1_over_limit_bal"] = bill / limit_denominator
        frame["pay_amt1_over_limit_bal"] = payment / limit_denominator
        frame["pay_amt1_over_abs_bill_amt1"] = payment / bill_denominator

        ratios = frame[list(RATIO_FEATURE_NAMES)].to_numpy(dtype=float)
        if not np.isfinite(ratios).all():
            raise ValueError("Financial ratios produced a non-finite value")
        return frame

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        """Names of the output columns, ratios appended."""
        if input_features is None:
            base = list(getattr(self, "feature_names_in_", []))
        else:
            base = list(input_features)
        return np.asarray([*base, *RATIO_FEATURE_NAMES], dtype=object)

    def _check_columns(self, X: pd.DataFrame) -> None:
        missing = [column for column in REQUIRED_COLUMNS if column not in X.columns]
        if missing:
            raise ValueError(f"Missing columns for the ratio features: {missing}")


def ratio_feature_names(base_features: list[str]) -> list[str]:
    """Internal feature list of a pipeline that uses the ratio transformer."""
    return [*base_features, *RATIO_FEATURE_NAMES]
