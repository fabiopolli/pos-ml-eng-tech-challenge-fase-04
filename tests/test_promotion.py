"""Tests of the promotion decision (plan 1.6, packages 1.6-O4 and 1.6-O5).

The criteria are exercised with controlled fixtures, so the boundaries of the
protocol are proved without needing an artificial gain on the real dataset.
"""

import copy
import json

import numpy as np
import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw
from sklearn.metrics import roc_auc_score

from credit_monitoring.config import feature_columns
from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.models.promotion import (
    bootstrap_paired_delta,
    evaluate_criteria,
    run_final_comparison,
    stratified_bootstrap_indices,
)
from credit_monitoring.models.tune import load_optimization_config, run_campaign

CRITERIA = {
    "min_gain_validation": 0.010,
    "min_gain_cv_mean": 0.005,
    "min_ablation_gain": 0.005,
    "ci_level": 0.95,
    "bootstrap_resamples": 200,
    "bootstrap_seed": 42,
}


def _candidate(roc_auc: float, *, ci_low: float = 0.01, integrity: bool = True) -> dict:
    return {
        "key": "random_forest_finalist",
        "metrics": {"roc_auc": roc_auc},
        "contrast": {"ci_low": ci_low, "ci_high": ci_low + 0.05},
        "integrity": {"passed": integrity, "detail": "fixture"},
    }


def _incumbent(roc_auc: float = 0.7741034702757726) -> dict:
    return {"key": "random_forest", "metrics": {"roc_auc": roc_auc}}


def test_a_gain_exactly_at_the_threshold_is_accepted():
    incumbent = _incumbent(0.7741034702757726)
    candidate = _candidate(0.7841034702757726)

    result = evaluate_criteria(
        candidate,
        incumbent,
        CRITERIA,
        cv_evidence={"cv_gain_over_control": 0.006},
        stability={"repetitions_beat_control": True},
    )

    assert result["checks"][0]["passed"] is True
    assert result["passed"] is True


def test_a_gain_below_the_threshold_is_rejected():
    incumbent = _incumbent(0.7741034702757726)
    candidate = _candidate(0.7841034702757726 - 0.0001)

    result = evaluate_criteria(
        candidate,
        incumbent,
        CRITERIA,
        cv_evidence={"cv_gain_over_control": 0.006},
        stability={"repetitions_beat_control": True},
    )

    assert result["checks"][0]["passed"] is False
    assert result["passed"] is False


def test_an_inconclusive_interval_blocks_the_promotion():
    incumbent = _incumbent(0.7741034702757726)
    candidate = _candidate(0.80, ci_low=-0.001)

    result = evaluate_criteria(
        candidate,
        incumbent,
        CRITERIA,
        cv_evidence={"cv_gain_over_control": 0.006},
        stability={"repetitions_beat_control": True},
    )

    assert result["checks"][2]["passed"] is False
    assert result["passed"] is False


def test_a_cv_gain_below_the_threshold_blocks_the_promotion():
    incumbent = _incumbent(0.7741034702757726)
    candidate = _candidate(0.80)

    result = evaluate_criteria(
        candidate,
        incumbent,
        CRITERIA,
        cv_evidence={"cv_gain_over_control": 0.004},
        stability={"repetitions_beat_control": True},
    )

    assert result["passed"] is False


def test_an_unstable_random_forest_is_not_promoted():
    incumbent = _incumbent(0.7741034702757726)
    candidate = _candidate(0.80)

    result = evaluate_criteria(
        candidate,
        incumbent,
        CRITERIA,
        cv_evidence={"cv_gain_over_control": 0.006},
        stability={"repetitions_beat_control": False},
    )

    assert result["passed"] is False
    assert any(
        check["criterion"] == "random_forest_repetitions_beat_control" for check in result["checks"]
    )


def test_a_failed_integrity_check_blocks_the_promotion():
    incumbent = _incumbent(0.7741034702757726)
    candidate = _candidate(0.80, integrity=False)

    result = evaluate_criteria(
        candidate,
        incumbent,
        CRITERIA,
        cv_evidence={"cv_gain_over_control": 0.006},
        stability={"repetitions_beat_control": True},
    )

    assert result["passed"] is False


def test_the_bootstrap_uses_the_same_indices_for_every_model():
    target = np.array([0] * 50 + [1] * 50)
    replicas = stratified_bootstrap_indices(target, 20, seed=42)

    assert len(replicas) == 20
    for rows in replicas:
        assert (target[rows] == 1).sum() == 50
        assert (target[rows] == 0).sum() == 50


def test_the_bootstrap_is_reproducible():
    target = np.array([0] * 50 + [1] * 50)
    first = stratified_bootstrap_indices(target, 20, seed=42)
    second = stratified_bootstrap_indices(target, 20, seed=42)

    for left, right in zip(first, second, strict=False):
        np.testing.assert_array_equal(left, right)


def test_the_interval_brackets_the_point_estimate():
    rng = np.random.default_rng(0)
    target = np.array([0] * 200 + [1] * 200)
    incumbent = target * 0.5 + rng.normal(0, 1.0, 400)
    candidate = target * 1.5 + rng.normal(0, 0.5, 400)

    result = bootstrap_paired_delta(
        target, incumbent, candidate, n_resamples=200, seed=42, ci_level=0.95
    )

    assert result["ci_low"] <= result["delta"] <= result["ci_high"]
    assert result["delta"] > 0


def test_the_metrics_are_recomputable_from_the_probabilities():
    rng = np.random.default_rng(1)
    target = pd.Series(np.array([0] * 100 + [1] * 100))
    probability = np.clip(target.to_numpy() * 0.6 + rng.normal(0, 0.4, 200), 0, 1)
    incumbent = np.clip(probability - 0.1, 0, 1)

    payload = run_final_comparison(
        {},
        {
            "experiment_id": "test",
            "protocol_version": "1",
            "criteria": CRITERIA,
            "threshold": 0.5,
            "primary_metric": "roc_auc",
        },
        target=target,
        probabilities={
            "random_forest": incumbent,
            "random_forest_finalist": probability,
        },
        models={
            "random_forest": {
                "key": "random_forest",
                "role": "incumbent",
                "algorithm": "random_forest",
            },
            "random_forest_finalist": {
                "key": "random_forest_finalist",
                "role": "finalist",
                "algorithm": "random_forest",
            },
        },
        incumbent_key="random_forest",
        cv_evidence={
            "random_forest_finalist": {
                "cv_gain_over_control": 0.02,
                "integrity": {"passed": True, "detail": "fixture"},
            }
        },
        stability={"repetitions_beat_control": True},
    )

    expected = roc_auc_score(target, probability)
    assert payload["models"]["random_forest_finalist"]["metrics_unrounded"]["roc_auc"] == (
        pytest.approx(expected, abs=1e-12)
    )
    assert payload["models"]["random_forest"]["metrics_unrounded"]["roc_auc"] == (
        pytest.approx(roc_auc_score(target, incumbent), abs=1e-12)
    )


def test_keep_current_when_no_candidate_satisfies_the_criteria():
    rng = np.random.default_rng(2)
    target = pd.Series(np.array([0] * 100 + [1] * 100))
    probability = target.to_numpy() * 0.5 + rng.normal(0, 1.0, 200)

    payload = run_final_comparison(
        {},
        {
            "experiment_id": "test",
            "protocol_version": "1",
            "criteria": CRITERIA,
            "threshold": 0.5,
            "primary_metric": "roc_auc",
        },
        target=target,
        probabilities={
            "random_forest": np.clip(probability, 0, 1),
            "random_forest_finalist": np.clip(probability, 0, 1),
        },
        models={
            "random_forest": {
                "key": "random_forest",
                "role": "incumbent",
                "algorithm": "random_forest",
            },
            "random_forest_finalist": {
                "key": "random_forest_finalist",
                "role": "finalist",
                "algorithm": "random_forest",
            },
        },
        incumbent_key="random_forest",
        cv_evidence={
            "random_forest_finalist": {
                "cv_gain_over_control": 0.0,
                "integrity": {"passed": True, "detail": "fixture"},
            }
        },
        stability={"repetitions_beat_control": True},
    )

    assert payload["decision"]["action"] == "keep_current"
    assert payload["decision"]["selected"] == "random_forest"
    assert payload["decision"]["kept_current"] is True


# ------------------------------------------------------------------ integration


@pytest.fixture
def optimization():
    protocol = copy.deepcopy(load_optimization_config())
    protocol["search"]["random_forest"]["n_draws"] = 2
    protocol["search"]["random_forest"]["grid"] = {
        "n_estimators": [20, 30],
        "max_depth": [4, None],
        "min_samples_leaf": [2, 5],
        "min_samples_split": [2, 10],
        "max_features": ["sqrt"],
        "class_weight": [None, "balanced"],
    }
    protocol["search"]["logistic_regression"]["max_iter"] = 500
    protocol["budget"]["max_fits"] = 200
    protocol["criteria"]["bootstrap_resamples"] = 100
    return protocol


@pytest.fixture
def processed_dir(tmp_path, config):
    raw = make_raw(config, rows=1000).rename(columns={RAW_TARGET: "default_payment_next_month"})
    prepared, _ = prepare_dataset(raw, config)
    directory = tmp_path / "processed"
    directory.mkdir()
    for name, frame in split_dataset(prepared, config).items():
        frame.to_csv(directory / f"{name}.csv", index=False)
    return directory


def test_the_selection_stage_freezes_the_decision_and_the_test_does_not_change_it(
    config, optimization, processed_dir, tmp_path
):
    from credit_monitoring.models.evaluate import run_evaluation
    from credit_monitoring.models.train import run_training

    reports = tmp_path / "reports"
    models = tmp_path / "models"
    run_campaign(
        config,
        optimization,
        processed_dir=processed_dir,
        reports_root=reports,
        models_root=models,
    )
    metrics = run_training(
        config,
        processed_dir=processed_dir,
        models_dir=models,
        reports_dir=reports,
        figures_dir=tmp_path / "figures",
        optimization=optimization,
    )

    decision = metrics["optimization"]["decision"]
    assert decision["action"] in {"promote", "keep_current"}
    comparison_path = (
        reports / "optimization" / optimization["experiment_id"] / "selection" / "comparison.json"
    )
    frozen = comparison_path.read_text(encoding="utf-8")

    metadata_before = (models / "credit_model_metadata.json").read_text(encoding="utf-8")
    run_evaluation(config, processed_dir=processed_dir, models_dir=models, reports_dir=reports)

    # The evaluation stage reads the frozen model and changes nothing about it.
    assert comparison_path.read_text(encoding="utf-8") == frozen
    assert (models / "credit_model_metadata.json").read_text(encoding="utf-8") == metadata_before
    assert (reports / "test_metrics.json").is_file()


def test_keep_current_keeps_the_incumbent_as_the_published_model(
    config, optimization, processed_dir, tmp_path
):
    from credit_monitoring.models.train import run_training

    reports = tmp_path / "reports"
    models = tmp_path / "models"
    run_campaign(
        config,
        optimization,
        processed_dir=processed_dir,
        reports_root=reports,
        models_root=models,
    )
    metrics = run_training(
        config,
        processed_dir=processed_dir,
        models_dir=models,
        reports_dir=reports,
        figures_dir=tmp_path / "figures",
        optimization=optimization,
    )
    metadata = json.loads((models / "credit_model_metadata.json").read_text(encoding="utf-8"))

    if metrics["optimization"]["decision"]["action"] == "keep_current":
        assert metadata["selected_version"]["kind"] == "incumbent"
        assert metadata["selected_version"]["decision"] == "keep_current"
        # The rejected finalist is never flagged as the published model.
        selected = [name for name, record in metadata["candidates"].items() if record["selected"]]
        assert selected == ["random_forest"]
        assert metadata["previous_model"]["sha256"]
        archive = models / "optimization" / optimization["experiment_id"] / "incumbent"
        assert (archive / "random_forest_current.joblib").is_file()


def test_a_promotion_publishes_the_finalist_and_archives_the_incumbent(
    config, optimization, processed_dir, tmp_path, monkeypatch
):
    """The wiring of the promotion: the finalist is published, the incumbent archived."""
    from credit_monitoring.models import train as train_module

    reports = tmp_path / "reports"
    models = tmp_path / "models"
    run_campaign(
        config,
        optimization,
        processed_dir=processed_dir,
        reports_root=reports,
        models_root=models,
    )

    original = train_module.run_final_comparison

    def promoting(*args, **kwargs):
        payload = original(*args, **kwargs)
        payload["decision"] = {
            "action": "promote",
            "selected": "random_forest_finalist",
            "reason": "forced by the test",
            "kept_current": False,
        }
        return payload

    monkeypatch.setattr(train_module, "run_final_comparison", promoting)
    metrics = train_module.run_training(
        config,
        processed_dir=processed_dir,
        models_dir=models,
        reports_dir=reports,
        figures_dir=tmp_path / "figures",
        optimization=optimization,
    )

    metadata = json.loads((models / "credit_model_metadata.json").read_text(encoding="utf-8"))
    assert metrics["optimization"]["decision"]["action"] == "promote"
    assert metadata["selected_version"]["kind"] == "optimized_finalist"
    assert metadata["selected_version"]["candidate_id"] == "random_forest_finalist"

    selected = [name for name, record in metadata["candidates"].items() if record["selected"]]
    assert selected == ["random_forest_finalist"]

    archive = models / "optimization" / optimization["experiment_id"] / "incumbent"
    assert (archive / "random_forest_current.joblib").is_file()

    # The published artifact reproduces the finalist: the probabilities are equal.
    import joblib

    validation = pd.read_csv(processed_dir / "validation.csv")
    features = feature_columns(config)
    published = joblib.load(models / "credit_model.joblib")
    finalist_path = (
        models
        / "optimization"
        / optimization["experiment_id"]
        / "finalists"
        / "random_forest.joblib"
    )
    finalist = joblib.load(finalist_path)
    np.testing.assert_allclose(
        published.predict_proba(validation[features])[:, 1],
        finalist.predict_proba(validation[features])[:, 1],
        atol=1e-12,
    )
    assert metadata["model_sha256"] != metadata["candidates"]["random_forest_finalist"]["sha256"]
    assert metadata["selected_version"]["published_from"]["candidate_id"] == (
        "random_forest_finalist"
    )


def test_the_published_model_predicts_with_the_manifest_features(
    config, optimization, processed_dir, tmp_path
):
    from credit_monitoring.models.train import run_training

    reports = tmp_path / "reports"
    models = tmp_path / "models"
    run_campaign(
        config,
        optimization,
        processed_dir=processed_dir,
        reports_root=reports,
        models_root=models,
    )
    run_training(
        config,
        processed_dir=processed_dir,
        models_dir=models,
        reports_dir=reports,
        figures_dir=tmp_path / "figures",
        optimization=optimization,
    )
    import joblib

    model = joblib.load(models / "credit_model.joblib")
    validation = pd.read_csv(processed_dir / "validation.csv")
    probability = model.predict_proba(validation[feature_columns(config)])
    assert probability.shape == (len(validation), 2)
