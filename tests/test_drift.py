import numpy as np
import pandas as pd
import pytest

from credit_monitoring.monitoring.drift import _render_html_report, calculate_psi


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


def test_report_is_brazilian_portuguese_didactic_and_preserves_comparison_results():
    def feature_result(feature, score, drift):
        return {
            "feature": feature,
            "score": score,
            "threshold": 0.2,
            "drift": drift,
            "reference_count": 10,
            "current_count": 5,
        }

    features = [
        feature_result("LIMIT_BAL", 0.75, True),
        feature_result("PAY_AMT1", 0.001, False),
    ]
    comparisons = [
        {
            "comparison_id": "reference_vs_original",
            "reference_rows": 10,
            "current_rows": 5,
            "drifted_feature_count": 0,
            "drifted_features": [],
            "global_alert": False,
            "features": [feature_result("LIMIT_BAL", 0.01, False), features[1]],
        },
        {
            "comparison_id": "reference_vs_modified",
            "reference_rows": 10,
            "current_rows": 5,
            "drifted_feature_count": 1,
            "drifted_features": ["LIMIT_BAL"],
            "global_alert": True,
            "features": features,
        },
        {
            "comparison_id": "original_vs_modified",
            "reference_rows": 5,
            "current_rows": 5,
            "drifted_feature_count": 1,
            "drifted_features": ["LIMIT_BAL"],
            "global_alert": True,
            "features": features,
        },
    ]
    probability_summary = {
        "rows": 5,
        "mean": 0.2,
        "p05": 0.01,
        "median": 0.1,
        "p95": 0.8,
        "predicted_positives": 1,
    }
    report = _render_html_report(
        comparisons=comparisons,
        probability_summaries={"original": probability_summary, "modified": probability_summary},
        metadata={
            "scenario_id": "phase-2-test",
            "protocol_version": "1.0.2",
            "protocol_sha256": "protocol-hash",
            "model_sha256": "model-hash",
            "contract_version": "1.0.0",
            "seed": 42,
            "persisted_probability_decimals": 12,
            "persisted_probability_rounding": "half_to_even",
            "model_training_versions": {"python": "3.12"},
            "reference_sha256": "ref-hash",
            "validation_sha256": "validation-hash",
            "original_sha256": "original-hash",
            "modified_sha256": "modified-hash",
            "manifest_sha256": "manifest-hash",
        },
        protocol={
            "features_to_shift": ["LIMIT_BAL", "PAY_AMT1"],
            "scenario": {"limit_bal_multiplier": 1.5, "pay_amt1_multiplier": 0.5},
            "psi": {
                "per_feature_threshold": 0.2,
                "reference_quantile_bins": 10,
                "smoothing": 1e-6,
            },
        },
        report_context={
            "dataset_section": "<div>Perfil do dataset</div>",
            "training_section": "<div>Estratégia e métricas</div>",
            "effect_section": "<div>Efeito nas pontuações</div>",
        },
        evidently_row_count=5,
        evidently_version="0.7.23",
    )

    assert 'lang="pt-BR"' in report
    assert 'data-report-template="pt-BR-5"' in report
    assert "Referência × controle original" in report
    assert "Referência × cenário modificado" in report
    assert "Controle original × cenário modificado" in report
    assert "O que significa PSI?" in report
    assert "p_lote,i − p_ref,i" in report
    assert "Limite de crédito (NT$)" in report
    assert "não um corte universal" in report
    assert "half-to-even (empate para o par)" in report
    assert "Perfil do dataset" in report
    assert "Estratégia e métricas" in report
    assert "Efeito nas pontuações" in report
    assert 'class="badge ok">Sem alerta' in report
    assert 'class="badge alert">Alerta' in report
    assert "Row count in dataset" not in report
    assert "Provenance and protocol" not in report
