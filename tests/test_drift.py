import numpy as np
import pandas as pd
import pytest

from credit_monitoring.monitoring.drift import calculate_psi


def test_psi_is_zero_for_identical_reference_and_current():
    values = pd.Series([0, 0, 1, 2, 3, 4, 5, 10, 20, 50])
    result = calculate_psi(values, values.copy(), feature="PAY_AMT1")

    assert result["score"] == 0.0
    assert result["drift"] is False
    assert np.isclose(sum(result["reference_proportions"]), 1.0)
    assert np.isclose(sum(result["current_proportions"]), 1.0)


def test_psi_separates_zero_mass_and_detects_a_known_shift():
    reference = pd.Series([0] * 80 + list(range(1, 21)))
    current = pd.Series([0] * 10 + list(range(1, 91)))
    result = calculate_psi(reference, current, feature="PAY_AMT1")

    assert result["drift"] is True
    assert result["score"] > 0.20
    assert result["reference_bin_counts"][0] == 80
    assert result["current_bin_counts"][0] == 10
    assert len(result["reference_bin_counts"]) <= 11


def test_psi_collapses_repeated_quantile_edges_and_keeps_open_extremes():
    reference = pd.Series([0] * 5 + [10] * 30 + [20] * 30 + [30] * 30 + [40] * 5)
    current = pd.Series([-100, 0, 10, 20, 30, 40, 1000] * 10)
    result = calculate_psi(reference, current, feature="LIMIT_BAL", max_bins=10)

    assert result["score"] >= 0.0
    assert len(result["bin_spec"]["edges"]) < 9
    assert sum(result["current_bin_counts"]) == len(current)
    assert np.isfinite(result["score"])


def test_psi_flags_values_outside_a_constant_reference():
    reference = pd.Series([5.0] * 100)
    current = pd.Series([5.0] * 50 + [6.0] * 50)
    result = calculate_psi(reference, current, feature="LIMIT_BAL")

    assert result["bin_spec"]["constant_value"] == 5.0
    assert result["drift"] is True


def test_threshold_comparison_is_strictly_greater_than():
    reference = pd.Series([0, 1, 2, 3, 4, 5])
    result = calculate_psi(reference, reference, feature="PAY_AMT1", threshold=0.0)

    assert result["score"] == 0.0
    assert result["drift"] is False


def test_psi_rejects_non_finite_values():
    with pytest.raises(ValueError, match="non-finite"):
        calculate_psi(pd.Series([1, np.inf]), pd.Series([1, 2]), feature="LIMIT_BAL")
