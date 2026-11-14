import json

import joblib
import numpy as np
import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw
from sklearn.ensemble import RandomForestClassifier

from credit_monitoring.config import feature_columns
from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.models.bias import (
    BIAS_REPORT_FILE,
    MIN_CLASS_SIZE,
    MIN_GROUP_SIZE,
    age_band,
    group_metrics,
    run_bias_analysis,
    wilson_interval,
)
from credit_monitoring.models.metrics import evaluate


@pytest.fixture
def frozen(tmp_path, config):
    """Small frozen model plus the selection record, without the Unix-only train stage."""
    raw = make_raw(config, rows=1500).rename(columns={RAW_TARGET: "default_payment_next_month"})
    prepared, _ = prepare_dataset(raw, config)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    splits = split_dataset(prepared, config)
    for name, frame in splits.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False)

    features = feature_columns(config)
    target = config["dataset"]["canonical_target"]
    model = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=0)
    model.fit(splits["train"][features], splits["train"][target])
    metrics = evaluate(model, splits["validation"][features], splits["validation"][target])

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    joblib.dump(model, models_dir / "credit_model.joblib")
    (models_dir / "credit_model_metadata.json").write_text(
        json.dumps({"selected_model": "random_forest", "features": features, "threshold": 0.5}),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "metrics.json").write_text(
        json.dumps(
            {
                "selected_model": "random_forest",
                "validation": {"random_forest": {"confusion_matrix": metrics["confusion_matrix"]}},
            }
        ),
        encoding="utf-8",
    )
    return processed_dir, models_dir, reports_dir


def test_wilson_interval_is_bounded_and_undefined_without_denominator():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(50, 100)
    assert 0.40 < low < 0.50 < high < 0.60
    assert wilson_interval(0, 40)[0] == 0.0
    assert wilson_interval(40, 40)[1] == 1.0


def test_group_metrics_suppresses_small_groups_and_marks_small_classes():
    target = np.array([1, 0] * (MIN_GROUP_SIZE // 2 - 1))
    assert group_metrics(target, target) == {"n": len(target), "status": "suppressed"}

    positives = MIN_CLASS_SIZE - 1
    target = np.array([1] * positives + [0] * 200)
    predicted = np.array([1] * positives + [0] * 200)
    metrics = group_metrics(target, predicted)
    assert metrics["status"] == "partial"
    assert metrics["tpr"]["value"] is None and metrics["tpr"]["denominator"] == positives
    assert metrics["fpr"]["value"] == 0.0 and metrics["fpr"]["status"] == "ok"
    assert metrics["confusion_matrix"] == {"tn": 200, "fp": 0, "fn": 0, "tp": positives}


def test_age_band_assigns_each_age_to_exactly_one_band():
    ages = pd.Series(range(18, 101))
    bands = age_band(ages)
    assert bands.notna().all()
    assert bands[ages == 29].item() == "<=29"
    assert bands[ages == 30].item() == "30-39"
    assert bands[ages == 50].item() == ">=50"


def test_bias_report_is_aggregated_and_never_opens_the_test_split(tmp_path, config, frozen):
    processed_dir, models_dir, reports_dir = frozen
    (processed_dir / "test.csv").unlink()

    payload = run_bias_analysis(
        config, processed_dir=processed_dir, models_dir=models_dir, reports_dir=reports_dir
    )

    written = json.loads((reports_dir / "bias" / BIAS_REPORT_FILE).read_text(encoding="utf-8"))
    assert written == payload
    assert payload["protocol"]["test_split_used"] is False
    rows = payload["overall"]["n"]
    assert rows == payload["protocol"]["partition_rows"]
    for column, groups in payload["groups"].items():
        assert sum(group["n"] for group in groups.values()) == rows, column
    assert "ID" not in json.dumps(payload)
    assert payload["reconciliation"]["validation_confusion_matrix_matches"] is True


def test_bias_analysis_refuses_a_run_that_does_not_reproduce_the_recorded_validation(
    tmp_path, config, frozen
):
    processed_dir, models_dir, reports_dir = frozen
    metrics_path = reports_dir / "metrics.json"
    recorded = json.loads(metrics_path.read_text(encoding="utf-8"))
    selected = recorded["selected_model"]
    recorded["validation"][selected]["confusion_matrix"]["tp"] += 1  # simulated stale model
    metrics_path.write_text(json.dumps(recorded), encoding="utf-8")

    with pytest.raises(ValueError, match="do not reproduce"):
        run_bias_analysis(
            config, processed_dir=processed_dir, models_dir=models_dir, reports_dir=reports_dir
        )
    assert not (reports_dir / "bias").exists()
