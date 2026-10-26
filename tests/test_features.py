"""Tests of the optional financial ratio features (plan 1.6, section 4.3)."""

import joblib
import numpy as np
import pandas as pd
import pytest

from credit_monitoring.models.features import (
    RATIO_FEATURE_NAMES,
    FinancialRatioTransformer,
    ratio_feature_names,
)


def _frame(**overrides) -> pd.DataFrame:
    base = {
        "LIMIT_BAL": [100_000.0, 100_000.0, 50_000.0, 10_000.0],
        "BILL_AMT1": [50_000.0, -20_000.0, 0.0, 30_000.0],
        "PAY_AMT1": [5_000.0, 0.0, 100.0, 30_000.0],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_ratios_follow_the_declared_formulas():
    frame = _frame()
    transformed = FinancialRatioTransformer().fit_transform(frame)

    np.testing.assert_allclose(
        transformed["bill_amt1_over_limit_bal"], frame["BILL_AMT1"] / frame["LIMIT_BAL"]
    )
    np.testing.assert_allclose(
        transformed["pay_amt1_over_limit_bal"], frame["PAY_AMT1"] / frame["LIMIT_BAL"]
    )
    np.testing.assert_allclose(
        transformed["pay_amt1_over_abs_bill_amt1"],
        frame["PAY_AMT1"] / frame["BILL_AMT1"].abs().clip(lower=1.0),
    )


def test_zero_payment_gives_a_zero_ratio_and_never_divides_by_zero():
    frame = _frame()
    transformed = FinancialRatioTransformer().fit_transform(frame)

    assert transformed["pay_amt1_over_limit_bal"].iloc[1] == 0.0
    assert transformed["pay_amt1_over_abs_bill_amt1"].iloc[1] == 0.0


def test_zero_invoice_uses_the_minimum_denominator_of_one():
    frame = _frame()
    transformed = FinancialRatioTransformer(min_denominator=1.0).fit_transform(frame)

    # Third ratio of the row with BILL_AMT1 == 0 uses max(abs(0), 1.0) == 1.0.
    assert transformed["pay_amt1_over_abs_bill_amt1"].iloc[2] == 100.0


def test_negative_invoice_keeps_its_sign_in_the_first_ratio():
    frame = _frame()
    transformed = FinancialRatioTransformer().fit_transform(frame)

    assert transformed["bill_amt1_over_limit_bal"].iloc[1] == pytest.approx(-0.2)
    # The third ratio uses the absolute value of the invoice.
    assert transformed["pay_amt1_over_abs_bill_amt1"].iloc[1] == pytest.approx(0.0)


def test_output_is_always_finite():
    frame = _frame(
        LIMIT_BAL=[0.0, -10.0, 100.0, 50.0],
        BILL_AMT1=[0.0, 0.0, 0.0, 0.0],
    )
    transformed = FinancialRatioTransformer().fit_transform(frame)

    values = transformed[list(RATIO_FEATURE_NAMES)].to_numpy(dtype=float)
    assert np.isfinite(values).all()


def test_external_inputs_are_preserved_and_the_ratios_are_appended():
    frame = _frame()
    transformed = FinancialRatioTransformer().fit_transform(frame)

    assert list(transformed.columns) == [*frame.columns, *RATIO_FEATURE_NAMES]
    np.testing.assert_allclose(
        transformed[list(frame.columns)].to_numpy(dtype=float),
        frame.to_numpy(dtype=float),
    )


def test_feature_names_out_lists_the_ratios_after_the_inputs():
    transformer = FinancialRatioTransformer().fit(_frame())

    names = list(transformer.get_feature_names_out())
    assert names[-3:] == list(RATIO_FEATURE_NAMES)
    assert ratio_feature_names(["A", "B"]) == ["A", "B", *RATIO_FEATURE_NAMES]


def test_missing_column_is_reported():
    with pytest.raises(ValueError, match="Missing columns"):
        FinancialRatioTransformer().fit(pd.DataFrame({"LIMIT_BAL": [1.0]}))


def test_reload_preserves_the_transformation_and_the_probabilities():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    frame = _frame()
    target = pd.Series([0, 1, 0, 1])
    pipeline = Pipeline(
        [
            ("ratios", FinancialRatioTransformer()),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(random_state=42)),
        ]
    )
    pipeline.fit(frame, target)
    before = pipeline.predict_proba(frame)[:, 1]

    reloaded = joblib.load(joblib.dump(pipeline, "/tmp/credit-monitoring-ratio-test.joblib")[0])
    after = reloaded.predict_proba(frame)[:, 1]

    np.testing.assert_allclose(before, after, atol=1e-12)
    assert "ratios" in reloaded.named_steps
