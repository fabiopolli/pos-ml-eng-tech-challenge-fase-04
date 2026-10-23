import json

import joblib
import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw

from credit_monitoring.config import feature_columns
from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.models.train import (
    METADATA_FILE,
    MODEL_FILE,
    build_models,
    run_training,
    select_best,
)


@pytest.fixture
def processed_dir(tmp_path, config):
    raw = make_raw(config, rows=1000).rename(columns={RAW_TARGET: "default_payment_next_month"})
    prepared, _ = prepare_dataset(raw, config)
    directory = tmp_path / "processed"
    directory.mkdir()
    for name, frame in split_dataset(prepared, config).items():
        frame.to_csv(directory / f"{name}.csv", index=False)
    return directory


def _train(tmp_path, config, processed_dir, label):
    return run_training(
        config,
        processed_dir=processed_dir,
        models_dir=tmp_path / label / "models",
        reports_dir=tmp_path / label / "reports",
        figures_dir=tmp_path / label / "figures",
    )


def test_build_models_follows_configured_candidates(config):
    assert list(build_models(config)) == ["logistic_regression", "random_forest"]


def test_build_models_rejects_unknown_candidate(config):
    config["modeling"]["candidates"].append("xgboost")
    with pytest.raises(ValueError):
        build_models(config)


def test_select_best_uses_highest_validation_metric_and_keeps_baseline_on_tie():
    validation = {"a": {"roc_auc": 0.7}, "b": {"roc_auc": 0.8}}
    assert select_best(validation, "roc_auc") == "b"
    assert select_best({"a": {"roc_auc": 0.8}, "b": {"roc_auc": 0.8}}, "roc_auc") == "a"


def test_run_training_writes_artifacts_and_metrics(tmp_path, config, processed_dir):
    metrics = _train(tmp_path, config, processed_dir, "run")
    base = tmp_path / "run"

    assert metrics["selected_model"] in config["modeling"]["candidates"]
    assert set(metrics["validation"]) == set(config["modeling"]["candidates"])
    for key in ("roc_auc", "precision", "recall", "f1", "accuracy", "confusion_matrix"):
        assert key in metrics["test"]
    assert json.loads((base / "reports" / "metrics.json").read_text(encoding="utf-8")) == metrics
    assert (base / "figures" / "01_roc_validation.png").is_file()
    assert (base / "figures" / "02_confusion_matrix_test.png").is_file()

    metadata = json.loads((base / "models" / METADATA_FILE).read_text(encoding="utf-8"))
    assert metadata["features"] == feature_columns(config)
    assert metadata["selected_model"] == metrics["selected_model"]

    model = joblib.load(base / "models" / MODEL_FILE)
    test = pd.read_csv(processed_dir / "test.csv")
    probability = model.predict_proba(test[feature_columns(config)])
    assert probability.shape == (len(test), 2)


def test_run_training_is_reproducible(tmp_path, config, processed_dir):
    first = _train(tmp_path, config, processed_dir, "first")
    second = _train(tmp_path, config, processed_dir, "second")
    assert first == second


def test_model_does_not_use_governance_features(config):
    assert not set(feature_columns(config)) & set(config["dataset"]["governance_features"])
