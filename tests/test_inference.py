"""Tests of the shared inference service (plan 1.6, package 1.6-O6).

The service is the single place where the contract, the feature selection and the
threshold are applied. These tests prove that an invalid batch never reaches a
model and that the probabilities are the ones of the frozen pipeline.
"""

import joblib
import numpy as np
import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw

from credit_monitoring.config import feature_columns
from credit_monitoring.contracts import ContractViolation
from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.models.inference import (
    ModelArtifactError,
    compare_models,
    divergence_summary,
    infer_batch,
    load_model,
    select_model_features,
)


@pytest.fixture
def processed_dir(tmp_path, config):
    raw = make_raw(config, rows=600).rename(columns={RAW_TARGET: "default_payment_next_month"})
    prepared, _ = prepare_dataset(raw, config)
    directory = tmp_path / "processed"
    directory.mkdir()
    for name, frame in split_dataset(prepared, config).items():
        frame.to_csv(directory / f"{name}.csv", index=False)
    return directory


@pytest.fixture
def model(config, processed_dir):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline

    train = pd.read_csv(processed_dir / "train.csv")
    pipeline = Pipeline(
        [
            (
                "classifier",
                RandomForestClassifier(n_estimators=20, max_depth=6, random_state=42, n_jobs=1),
            )
        ]
    )
    pipeline.fit(train[feature_columns(config)], train[config["dataset"]["canonical_target"]])
    return pipeline


def _batch(processed_dir, config, rows: int = 3) -> pd.DataFrame:
    validation = pd.read_csv(processed_dir / "validation.csv").head(rows)
    return validation.drop(columns=[config["dataset"]["canonical_target"]])


def test_the_probabilities_are_the_ones_of_the_frozen_pipeline(model, processed_dir, config):
    batch = _batch(processed_dir, config)
    result = infer_batch(model, batch, config)

    expected = model.predict_proba(batch[feature_columns(config)])[:, 1]
    np.testing.assert_allclose(result.probability, expected, atol=1e-12)
    np.testing.assert_array_equal(result.predicted, (expected >= 0.5).astype(int))


def test_an_invalid_batch_is_rejected_before_any_model_call(
    model, processed_dir, config, monkeypatch
):
    """A violated contract means zero calls to the model."""
    batch = _batch(processed_dir, config)
    batch.loc[batch.index[0], "LIMIT_BAL"] = 0.0

    calls = []

    class Spy:
        def predict_proba(self, features):
            calls.append(features)
            return model.predict_proba(features)

    with pytest.raises(ContractViolation):
        infer_batch(Spy(), batch, config)

    assert calls == []


def test_compare_models_validates_once_and_scores_every_model(model, processed_dir, config):
    batch = _batch(processed_dir, config)
    comparison = compare_models({"a": model, "b": model}, batch, config)

    assert comparison["rows"] == len(batch)
    assert set(comparison["probabilities"]) == {"a", "b"}
    np.testing.assert_allclose(
        comparison["probabilities"]["a"], comparison["probabilities"]["b"], atol=0
    )


def test_compare_models_rejects_the_whole_batch(model, processed_dir, config, monkeypatch):
    batch = _batch(processed_dir, config)
    batch.loc[batch.index[0], "AGE"] = 500.0

    calls = []
    original = model.predict_proba

    def counting(features):
        calls.append(features)
        return original(features)

    monkeypatch.setattr(model, "predict_proba", counting)
    with pytest.raises(ContractViolation):
        compare_models({"a": model}, batch, config)

    assert calls == []


def test_the_feature_selection_uses_the_manifest_order(model, processed_dir, config):
    batch = _batch(processed_dir, config)
    features = feature_columns(config)
    shuffled = batch[list(reversed(list(batch.columns)))]

    selected = select_model_features(shuffled, config, features)
    assert list(selected.columns) == features

    result = infer_batch(model, shuffled, config)
    expected = model.predict_proba(batch[features])[:, 1]
    np.testing.assert_allclose(result.probability, expected, atol=1e-12)


def test_a_missing_feature_is_rejected_by_the_contract_first(model, processed_dir, config):
    """The contract gate precedes the feature selection: the batch is rejected whole."""
    batch = _batch(processed_dir, config).drop(columns=["PAY_AMT1"])
    with pytest.raises(ContractViolation):
        infer_batch(model, batch, config)


def test_the_feature_selection_reports_a_missing_input(model, processed_dir, config):
    batch = _batch(processed_dir, config)
    with pytest.raises(ModelArtifactError, match="Missing model inputs"):
        select_model_features(batch, config, [*feature_columns(config), "OUTLIER"])


def test_the_divergence_is_reported_between_the_models(model, processed_dir, config):
    batch = _batch(processed_dir, config)
    comparison = compare_models({"a": model, "b": model}, batch, config)
    divergence = divergence_summary(comparison)

    assert divergence["max_abs_difference"] == 0.0
    assert divergence["rows_with_divergence"] == 0


def test_load_model_refuses_an_artifact_that_does_not_match_the_hash(model, tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump(model, path)

    loaded = load_model(path)
    assert loaded is not None
    with pytest.raises(ModelArtifactError, match="hash mismatch"):
        load_model(path, expected_sha256="0" * 64)
    with pytest.raises(ModelArtifactError, match="not found"):
        load_model(tmp_path / "missing.joblib")
