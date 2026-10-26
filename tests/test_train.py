import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw

from credit_monitoring.config import feature_columns
from credit_monitoring.contracts import ContractViolation
from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.models.train import (
    METADATA_FILE,
    MODEL_FILE,
    build_models,
    evaluate,
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


def test_select_best_uses_highest_validation_metric():
    validation = {"a": {"roc_auc": 0.7}, "b": {"roc_auc": 0.8}}
    assert select_best(validation, "roc_auc") == "b"


def test_select_best_keeps_baseline_on_tie():
    validation = {"logistic_regression": {"roc_auc": 0.8}, "random_forest": {"roc_auc": 0.8}}
    assert (
        select_best(validation, "roc_auc", baseline="logistic_regression") == "logistic_regression"
    )


def test_select_break_tie_without_baseline_is_deterministic():
    validation = {"random_forest": {"roc_auc": 0.8}, "xgboost": {"roc_auc": 0.8}}
    first = select_best(validation, "roc_auc", baseline="logistic_regression")
    second = select_best(
        {"xgboost": {"roc_auc": 0.8}, "random_forest": {"roc_auc": 0.8}},
        "roc_auc",
        baseline="logistic_regression",
    )
    assert first == second


def test_select_best_rejects_empty_validation():
    with pytest.raises(ValueError):
        select_best({}, "roc_auc")


def test_selection_uses_unrounded_metrics():
    """Candidates inside the reporting grid are not a tie when the raw values differ."""
    validation = {
        "logistic_regression": {"roc_auc": 0.80000004},
        "random_forest": {"roc_auc": 0.8},
    }
    # Unrounded: logistic_regression is strictly better.
    assert (
        select_best(validation, "roc_auc", baseline="logistic_regression") == "logistic_regression"
    )
    # Rounded for reporting, the same two candidates tie and the baseline would win.
    rounded = {
        name: {"roc_auc": round(values["roc_auc"], 6)} for name, values in validation.items()
    }
    assert select_best(rounded, "roc_auc", baseline="random_forest") == "random_forest"


def test_run_training_writes_artifacts_and_metrics(tmp_path, config, processed_dir):
    metrics = _train(tmp_path, config, processed_dir, "run")
    base = tmp_path / "run"

    assert metrics["selected_model"] in config["modeling"]["candidates"]
    assert set(metrics["validation"]) == set(config["modeling"]["candidates"])
    for key in ("roc_auc", "precision", "recall", "f1", "accuracy", "confusion_matrix"):
        assert key in metrics["validation"][metrics["selected_model"]]
    assert "test" not in metrics
    assert json.loads((base / "reports" / "metrics.json").read_text(encoding="utf-8")) == metrics
    assert (base / "figures" / "01_roc_validation.png").is_file()
    assert (base / "figures" / "02_confusion_matrix_validation.png").is_file()

    metadata = json.loads((base / "models" / METADATA_FILE).read_text(encoding="utf-8"))
    assert metadata["features"] == feature_columns(config)
    assert metadata["selected_model"] == metrics["selected_model"]

    model = joblib.load(base / "models" / MODEL_FILE)
    validation = pd.read_csv(processed_dir / "validation.csv")
    probability = model.predict_proba(validation[feature_columns(config)])
    assert probability.shape == (len(validation), 2)
    assert ((probability >= 0) & (probability <= 1)).all()


def test_run_training_is_reproducible(tmp_path, config, processed_dir):
    first = _train(tmp_path, config, processed_dir, "first")
    second = _train(tmp_path, config, processed_dir, "second")
    assert first == second


def test_model_does_not_use_governance_features(config):
    assert not set(feature_columns(config)) & set(config["dataset"]["governance_features"])


def test_selection_runs_without_the_test_split(tmp_path, config, processed_dir):
    """Isolation by behaviour: the selection stage must not need the test file."""
    isolated = tmp_path / "without-test"
    isolated.mkdir()
    for name in ("train", "validation"):
        (isolated / f"{name}.csv").write_bytes((processed_dir / f"{name}.csv").read_bytes())

    metrics = run_training(
        config,
        processed_dir=isolated,
        models_dir=tmp_path / "models",
        reports_dir=tmp_path / "reports",
        figures_dir=tmp_path / "figures",
    )
    assert metrics["selected_model"] in config["modeling"]["candidates"]


def test_contract_violation_stops_the_fit(tmp_path, config, processed_dir, monkeypatch):
    """A violated contract must abort before any estimator is fitted."""
    invalid = pd.read_csv(processed_dir / "train.csv")
    invalid.loc[invalid.index[0], "LIMIT_BAL"] = 0
    invalid.to_csv(processed_dir / "train.csv", index=False)

    calls = []
    from sklearn.pipeline import Pipeline

    original_fit = Pipeline.fit

    def counting_fit(self, *args, **kwargs):
        calls.append(self)
        return original_fit(self, *args, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", counting_fit)

    with pytest.raises(ContractViolation):
        _train(tmp_path, config, processed_dir, "invalid")

    assert calls == []


def test_metadata_is_complete(tmp_path, config, processed_dir):
    _train(tmp_path, config, processed_dir, "meta")
    metadata = json.loads(
        (tmp_path / "meta" / "models" / METADATA_FILE).read_text(encoding="utf-8")
    )
    for key in (
        "threshold",
        "features",
        "random_seed",
        "config_sha256",
        "train_sha256",
        "validation_sha256",
        "model_sha256",
        "git_sha",
        "contract_version",
        "test_exposure",
        "reload_check",
        "versions",
    ):
        assert key in metadata
    assert metadata["threshold"] == 0.5
    assert metadata["reload_check"]["passed"] is True
    assert metadata["test_exposure"]["declared"] is True
    assert metadata["versions"]["scikit-learn"]
    assert metadata["versions"]["pandas"]


def test_reload_check_compares_probabilities_within_tolerance(tmp_path, config, processed_dir):
    _train(tmp_path, config, processed_dir, "reload")
    metrics = json.loads((tmp_path / "reload" / "reports" / "metrics.json").read_text("utf-8"))
    assert metrics["reload_check"]["passed"] is True
    assert (
        metrics["reload_check"]["max_abs_probability_difference"]
        <= metrics["reload_check"]["tolerance"]
    )


def test_convergence_is_reported(tmp_path, config, processed_dir):
    _train(tmp_path, config, processed_dir, "convergence")
    metrics = json.loads((tmp_path / "convergence" / "reports" / "metrics.json").read_text("utf-8"))
    for name in config["modeling"]["candidates"]:
        assert metrics["fit"][name]["converged"] is True
        assert metrics["fit"][name]["convergence_warnings"] == []


def test_resource_measurements_are_recorded_outside_the_tracked_artifacts(
    tmp_path, config, processed_dir
):
    _train(tmp_path, config, processed_dir, "resources")
    resources = json.loads(
        (tmp_path / "resources" / "reports" / "run_resources.json").read_text(encoding="utf-8")
    )
    assert set(resources["per_model"]) == set(config["modeling"]["candidates"])
    for cost in resources["per_model"].values():
        assert cost["wall_time_s"] >= 0
        assert cost["cpu_time_s"] >= 0
        assert cost["method"]
    metrics = json.loads((tmp_path / "resources" / "reports" / "metrics.json").read_text("utf-8"))
    assert "resources" not in metrics


def test_evaluate_returns_unrounded_metrics(tmp_path, config, processed_dir):
    _train(tmp_path, config, processed_dir, "unrounded")
    model = joblib.load(tmp_path / "unrounded" / "models" / MODEL_FILE)
    validation = pd.read_csv(processed_dir / "validation.csv")
    metrics = evaluate(
        model, validation[feature_columns(config)], validation["default_payment_next_month"]
    )
    assert 0.0 < metrics["roc_auc"] < 1.0


def test_model_file_exists_after_training(tmp_path, config, processed_dir):
    _train(tmp_path, config, processed_dir, "files")
    assert (tmp_path / "files" / "models" / MODEL_FILE).is_file()
    assert Path(tmp_path / "files" / "models" / METADATA_FILE).is_file()
