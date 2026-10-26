"""Tests of the optimization campaign (plan 1.6, packages 1.6-O1 to 1.6-O3).

The campaign is the most constrained piece of the project: it reads **only** the
training split, it fits inside the folds, it respects a declared budget and it
records its failures. These tests prove each of those properties by behaviour.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw
from sklearn.preprocessing import StandardScaler

from credit_monitoring.config import feature_columns
from credit_monitoring.data.prepare import prepare_dataset
from credit_monitoring.models import tune
from credit_monitoring.models.tune import (
    BudgetExceeded,
    build_folds,
    build_trial_list,
    load_optimization_config,
    load_training_split,
    rank_trials,
    run_campaign,
)

TRAIN_ROWS = 600


@pytest.fixture
def optimization():
    """A small protocol: the same rules, smaller trees, so the test stays fast."""
    protocol = copy.deepcopy(load_optimization_config())
    protocol["search"]["random_forest"]["n_draws"] = 3
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
    protocol["criteria"]["bootstrap_resamples"] = 50
    return protocol


@pytest.fixture
def train_only_dir(tmp_path, config):
    """A processed directory that holds **only** the training split."""
    raw = make_raw(config, rows=TRAIN_ROWS).rename(
        columns={RAW_TARGET: "default_payment_next_month"}
    )
    prepared, _ = prepare_dataset(raw, config)
    directory = tmp_path / "processed"
    directory.mkdir()
    prepared.to_csv(directory / "train.csv", index=False)
    return directory


def _run(config, optimization, train_only_dir, tmp_path, label="run"):
    return run_campaign(
        config,
        optimization,
        processed_dir=train_only_dir,
        reports_root=tmp_path / label / "reports",
        models_root=tmp_path / label / "models",
    )


def test_campaign_runs_without_the_validation_and_the_test_splits(
    config, optimization, train_only_dir, tmp_path
):
    payload = _run(config, optimization, train_only_dir, tmp_path)

    assert set(payload["finalists"]) == {"logistic_regression", "random_forest"}
    for record in payload["finalists"].values():
        assert record["converged"] is True
        assert record["sha256"]
        assert record["cv_mean_roc_auc"] is not None


def test_campaign_reads_only_the_training_file(
    config, optimization, train_only_dir, tmp_path, monkeypatch
):
    """The campaign has no code path that opens the validation or the test split."""
    import pandas as pd

    reads: list[str] = []
    original = pd.read_csv

    def recording(path, *args, **kwargs):
        reads.append(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", recording)
    _run(config, optimization, train_only_dir, tmp_path)

    assert reads, "the campaign did not read anything"
    assert all(path.endswith("train.csv") for path in reads), reads


def test_accessing_another_split_is_refused(config, tmp_path):
    with pytest.raises(ValueError, match="train split"):
        load_training_split(tmp_path, config, split="validation")
    with pytest.raises(ValueError, match="train split"):
        load_training_split(tmp_path, config, split="test")


def test_scaler_is_fitted_inside_the_fold_only(
    config, optimization, train_only_dir, tmp_path, monkeypatch
):
    """The scaler never sees the whole training set before the cross-validation."""
    rows: list[int] = []
    original = StandardScaler.fit

    def recording(self, X, y=None, sample_weight=None):
        rows.append(len(X))
        return original(self, X, y, sample_weight)

    monkeypatch.setattr(StandardScaler, "fit", recording)
    _run(config, optimization, train_only_dir, tmp_path)

    frame = pd.read_csv(train_only_dir / "train.csv")
    total = len(frame)
    folds = build_folds(frame[config["dataset"]["canonical_target"]], optimization["folds"])
    expected = {len(train_index) for train_index, _ in folds}

    assert rows, "the scaler was never fitted"
    fold_fits = [count for count in rows if count < total]
    assert set(fold_fits) <= expected
    # Only the final adjustment of the finalist uses the whole training split.
    assert rows.count(total) == 1


def test_a_failure_is_recorded_and_never_becomes_a_zero_score(
    config, optimization, train_only_dir, tmp_path, monkeypatch
):
    """A configuration that fails keeps its place in the attempts and has no score."""
    original = tune.fit_with_convergence

    def failing(model, x_train, y_train):
        classifier = model.named_steps.get("classifier")
        if classifier is not None and getattr(classifier, "C", None) == 100.0:
            raise RuntimeError("boom")
        return original(model, x_train, y_train)

    monkeypatch.setattr(tune, "fit_with_convergence", failing)
    _run(config, optimization, train_only_dir, tmp_path)

    trials = json.loads(
        (
            Path(tmp_path)
            / "run"
            / "reports"
            / "optimization"
            / optimization["experiment_id"]
            / "tuning"
            / "trials.json"
        ).read_text(encoding="utf-8")
    )["trials"]

    failed = [trial for trial in trials if trial["status"] == "failed"]
    successful = [trial for trial in trials if trial["status"] == "ok"]
    assert failed, "the failing configuration was not recorded"
    assert successful, "the campaign did not continue after the failure"
    for trial in failed:
        assert trial["mean_roc_auc"] is None
        assert trial["std_roc_auc"] is None
        assert trial["failure"]
    # The failed attempts stay in the count: they are not removed from the campaign.
    assert len(trials) == len(failed) + len(successful)
    assert sum(1 for trial in failed if trial["algorithm"] == "logistic_regression") == 2


def test_no_identifier_target_or_governance_attribute_enters_the_estimator(
    config, optimization, train_only_dir, tmp_path, monkeypatch
):
    from sklearn.pipeline import Pipeline

    seen: list[list[str]] = []
    original = Pipeline.fit

    def recording(self, X, y, *args, **kwargs):
        seen.append(list(X.columns))
        return original(self, X, y, *args, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", recording)
    _run(config, optimization, train_only_dir, tmp_path)

    features = feature_columns(config)
    assert seen
    for columns in seen:
        assert columns == features
    assert "ID" not in features
    assert config["dataset"]["canonical_target"] not in features
    assert not set(config["dataset"]["governance_features"]) & set(features)


def test_trials_folds_and_configuration_are_reproducible(
    config, optimization, train_only_dir, tmp_path
):
    first = _run(config, optimization, train_only_dir, tmp_path, "first")
    second = _run(config, optimization, train_only_dir, tmp_path, "second")

    root = Path(tmp_path) / "first" / "reports" / "optimization" / optimization["experiment_id"]
    other = Path(tmp_path) / "second" / "reports" / "optimization" / optimization["experiment_id"]
    for name in ("manifest.json", "trials.json", "ablation.json", "stability.json"):
        assert (root / "tuning" / name).read_text(encoding="utf-8") == (
            other / "tuning" / name
        ).read_text(encoding="utf-8")

    for algorithm in first["finalists"]:
        assert (
            first["finalists"][algorithm]["cv_mean_roc_auc"]
            == second["finalists"][algorithm]["cv_mean_roc_auc"]
        )
        assert first["finalists"][algorithm]["sha256"] == second["finalists"][algorithm]["sha256"]


def test_the_trial_list_is_persisted_before_the_results(
    config, optimization, train_only_dir, tmp_path
):
    _run(config, optimization, train_only_dir, tmp_path)
    manifest = json.loads(
        (
            Path(tmp_path)
            / "run"
            / "reports"
            / "optimization"
            / optimization["experiment_id"]
            / "tuning"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["state"] == "protocol_frozen_before_results"
    assert len(manifest["trial_lists"]["random_forest"]) == 3
    assert len(manifest["trial_lists"]["logistic_regression"]) == 12
    assert manifest["inputs"]["train_sha256"]
    assert manifest["versions"]["scikit-learn"]
    assert manifest["sources"]
    assert manifest["folds"]["fingerprint"]


def test_the_budget_stops_the_campaign_instead_of_running_it_partially(
    config, optimization, train_only_dir, tmp_path
):
    optimization["budget"]["max_fits"] = 3
    with pytest.raises(BudgetExceeded):
        _run(config, optimization, train_only_dir, tmp_path)


def test_rank_trials_prefers_the_control_on_an_exact_tie():
    trials = [
        {"trial_id": "a:control:00", "status": "ok", "mean_roc_auc": 0.8},
        {"trial_id": "a:search:01", "status": "ok", "mean_roc_auc": 0.8},
    ]
    assert rank_trials(trials, "a:control:00") == "a:control:00"


def test_rank_trials_keeps_the_first_of_the_tied_new_configurations():
    trials = [
        {"trial_id": "a:control:00", "status": "ok", "mean_roc_auc": 0.7},
        {"trial_id": "a:search:01", "status": "ok", "mean_roc_auc": 0.8},
        {"trial_id": "a:search:02", "status": "ok", "mean_roc_auc": 0.8},
    ]
    assert rank_trials(trials, "a:control:00") == "a:search:01"


def test_rank_trials_ignores_failed_trials():
    trials = [
        {"trial_id": "a:control:00", "status": "ok", "mean_roc_auc": 0.7},
        {"trial_id": "a:search:01", "status": "failed", "mean_roc_auc": None},
    ]
    assert rank_trials(trials, "a:control:00") == "a:control:00"


def test_the_trial_list_is_distinct_and_the_logistic_grid_is_complete(optimization):
    trial_list = build_trial_list(optimization)
    forest = trial_list["random_forest"]
    signatures = {json.dumps(params, sort_keys=True, default=str) for params in forest}
    assert len(signatures) == len(forest)

    logistic = trial_list["logistic_regression"]
    assert len(logistic) == 12
    assert {params["C"] for params in logistic} == {
        0.001,
        0.01,
        0.1,
        1.0,
        10.0,
        100.0,
    }
    assert {params["class_weight"] for params in logistic} == {None, "balanced"}


def test_folds_are_the_same_partition_for_every_candidate(config, optimization):
    frame = pd.DataFrame({"target": [0, 1] * 50})
    first = build_folds(frame["target"], optimization["folds"])
    second = build_folds(frame["target"], optimization["folds"])

    for (train_a, valid_a), (train_b, valid_b) in zip(first, second, strict=False):
        np.testing.assert_array_equal(train_a, train_b)
        np.testing.assert_array_equal(valid_a, valid_b)
    assert len(first) == optimization["folds"]["n_splits"]
