"""Pure validation tests for the aggregate-only Data Drift snapshot."""

import hashlib
import json

import pytest

from credit_monitoring.monitoring.drift_snapshot import (
    COMPARISON_IDS,
    FEATURES,
    INPUT_SHA256,
    MODEL_SHA256,
    DriftSnapshotError,
    load_drift_snapshot,
)

SCENARIO = "phase-2-1.0.2"
PROTOCOL = "1.0.2"
CONTRACT = "1.0.0"
MODEL_HASH = MODEL_SHA256
ORIGINAL_HASH = INPUT_SHA256["original"]
MODIFIED_HASH = INPUT_SHA256["modified"]
SUMMARIES = {
    "original": {
        "rows": 4500,
        "predicted_positives": 1161,
        "mean": 0.423073079990242,
        "median": 0.36625336787999996,
        "p05": 0.20204244476810002,
        "p25": 0.273929924244,
        "p75": 0.5048897824495,
        "p95": 0.85023558377615,
        "std_population": 0.19908546777397865,
    },
    "modified": {
        "rows": 4500,
        "predicted_positives": 1154,
        "mean": 0.4198523230775716,
        "median": 0.3641660657375,
        "p05": 0.19953737306795002,
        "p25": 0.26681830506899995,
        "p75": 0.50599646070275,
        "p95": 0.84766798406205,
        "std_population": 0.1993956775595381,
    },
}


def _feature(name, *, drift=False):
    return {
        "feature": name,
        "method": "custom_psi",
        "comparison": ">",
        "score": 0.25 if drift else 0.1,
        "threshold": 0.2,
        "drift": drift,
        "reference_count": 21_000,
        "current_count": 4_500,
        "bin_spec": {
            "labels": ["zero", "qbin_00", "qbin_01"],
            "edges": [10.0],
            "zero_separate": True,
        },
        "reference_bin_counts": [4_200, 8_400, 8_400],
        "current_bin_counts": [900, 1_800, 1_800],
        "reference_proportions": [0.2, 0.4, 0.4],
        "current_proportions": [0.2, 0.4, 0.4],
    }


def _comparison(comparison_id):
    reference_rows = 21_000 if comparison_id.startswith("reference_") else 4_500
    items = []
    for feature in FEATURES:
        drift = comparison_id != COMPARISON_IDS[0] and feature in {"LIMIT_BAL", "PAY_AMT1"}
        item = _feature(feature, drift=drift)
        item["reference_count"] = reference_rows
        item["reference_bin_counts"] = (
            [4_200, 8_400, 8_400] if reference_rows == 21_000 else [900, 1_800, 1_800]
        )
        items.append(item)
    drifted = [item["feature"] for item in items if item["drift"]]
    return {
        "comparison_id": comparison_id,
        "reference_rows": reference_rows,
        "current_rows": 4_500,
        "drifted_feature_count": len(drifted),
        "drifted_features": drifted,
        "global_alert": bool(drifted),
        "global_alert_rule": "any_feature_exceeds_threshold",
        "method": "custom_psi",
        "features": items,
    }


def _write_snapshot(reports_dir):
    drift_dir = reports_dir / "drift"
    drift_dir.mkdir(parents=True)
    predictions = {
        "schema_version": "1.0.0",
        "scenario_id": SCENARIO,
        "protocol_version": PROTOCOL,
        "contract_version": CONTRACT,
        "model_sha256": MODEL_HASH,
        "threshold": 0.5,
        "input_sha256": {"original": ORIGINAL_HASH, "modified": MODIFIED_HASH},
        "inference": {
            name: {
                "rows": 4500,
                "predicted_positives": SUMMARIES[name]["predicted_positives"],
                "mean_probability": SUMMARIES[name]["mean"],
                "model_sha256": MODEL_HASH,
                "threshold": 0.5,
            }
            for name in ("original", "modified")
        },
        "predictions": {
            name: {"sha256": "3" * 64, "summary": SUMMARIES[name]}
            for name in ("original", "modified")
        },
    }
    prediction_bytes = json.dumps(predictions, sort_keys=True).encode()
    (drift_dir / "prediction_summary-v1.0.2.json").write_bytes(prediction_bytes)
    results = {
        "schema_version": "1.0.0",
        "scenario_id": SCENARIO,
        "protocol_version": PROTOCOL,
        "contract_version": CONTRACT,
        "model_sha256": MODEL_HASH,
        "threshold_model": 0.5,
        "feature_set": list(FEATURES),
        "hashes": {
            "original": ORIGINAL_HASH,
            "modified": MODIFIED_HASH,
            "prediction_summary": hashlib.sha256(prediction_bytes).hexdigest(),
        },
        "comparisons": [_comparison(comparison_id) for comparison_id in COMPARISON_IDS],
        "probability_summaries": SUMMARIES,
    }
    (drift_dir / "results-v1.0.2.json").write_text(json.dumps(results), encoding="utf-8")
    return results


def test_loads_the_three_aggregate_comparisons(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_snapshot(reports_dir)

    snapshot = load_drift_snapshot(reports_dir)

    assert snapshot.model_sha256 == MODEL_HASH
    assert [item.comparison_id for item in snapshot.comparisons] == list(COMPARISON_IDS)
    assert snapshot.comparisons[0].drifted_features == ()
    assert snapshot.comparisons[1].drifted_features == ("LIMIT_BAL", "PAY_AMT1")
    assert len(snapshot.comparisons[2].features) == 19
    assert snapshot.original.rows == snapshot.modified.rows == 4500


def test_missing_artifact_has_a_controlled_message(tmp_path):
    with pytest.raises(DriftSnapshotError, match="Artefato ausente"):
        load_drift_snapshot(tmp_path / "reports")


def test_unsupported_schema_is_rejected(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_snapshot(reports_dir)
    path = reports_dir / "drift" / "results-v1.0.2.json"
    results = json.loads(path.read_text())
    results["schema_version"] = "99.0.0"
    path.write_text(json.dumps(results), encoding="utf-8")

    with pytest.raises(DriftSnapshotError, match="schema_version"):
        load_drift_snapshot(reports_dir)


def test_hash_mismatch_is_rejected(tmp_path):
    reports_dir = tmp_path / "reports"
    results = _write_snapshot(reports_dir)
    results["hashes"]["prediction_summary"] = "4" * 64
    path = reports_dir / "drift" / "results-v1.0.2.json"
    path.write_text(json.dumps(results), encoding="utf-8")

    with pytest.raises(DriftSnapshotError, match="hash do resumo"):
        load_drift_snapshot(reports_dir)


def test_alert_mismatch_is_rejected(tmp_path):
    reports_dir = tmp_path / "reports"
    results = _write_snapshot(reports_dir)
    results["comparisons"][0]["features"][0]["drift"] = True
    path = reports_dir / "drift" / "results-v1.0.2.json"
    path.write_text(json.dumps(results), encoding="utf-8")

    with pytest.raises(DriftSnapshotError, match="alerta de LIMIT_BAL"):
        load_drift_snapshot(reports_dir)


def test_non_finite_bin_proportion_is_rejected(tmp_path):
    reports_dir = tmp_path / "reports"
    results = _write_snapshot(reports_dir)
    results["comparisons"][0]["features"][0]["reference_proportions"][0] = float("nan")
    path = reports_dir / "drift" / "results-v1.0.2.json"
    path.write_text(json.dumps(results), encoding="utf-8")

    with pytest.raises(DriftSnapshotError, match="fora do domínio"):
        load_drift_snapshot(reports_dir)
