import json

import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw

from credit_monitoring.contracts import ContractViolation
from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.models.evaluate import TEST_METRICS_FILE, run_evaluation
from credit_monitoring.models.train import METADATA_FILE, MODEL_FILE, run_training


@pytest.fixture
def processed_dir(tmp_path, config):
    raw = make_raw(config, rows=1000).rename(columns={RAW_TARGET: "default_payment_next_month"})
    prepared, _ = prepare_dataset(raw, config)
    directory = tmp_path / "processed"
    directory.mkdir()
    for name, frame in split_dataset(prepared, config).items():
        frame.to_csv(directory / f"{name}.csv", index=False)
    return directory


@pytest.fixture
def frozen(tmp_path, config, processed_dir):
    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"
    run_training(
        config,
        processed_dir=processed_dir,
        models_dir=models_dir,
        reports_dir=reports_dir,
        figures_dir=tmp_path / "figures",
    )
    return models_dir, reports_dir


def test_evaluation_writes_test_metrics(tmp_path, config, processed_dir, frozen):
    models_dir, reports_dir = frozen
    payload = run_evaluation(
        config,
        processed_dir=processed_dir,
        models_dir=models_dir,
        reports_dir=reports_dir,
    )
    assert payload["selected_model"]
    for key in ("roc_auc", "precision", "recall", "f1", "accuracy", "confusion_matrix"):
        assert key in payload["test"]
    written = json.loads((reports_dir / TEST_METRICS_FILE).read_text(encoding="utf-8"))
    assert written == payload
    assert written["protocol"]["frozen"] is True
    assert written["test_exposure"]["declared"] is True


def test_evaluation_does_not_change_the_selection(tmp_path, config, processed_dir, frozen):
    models_dir, reports_dir = frozen
    metadata_before = (models_dir / METADATA_FILE).read_text(encoding="utf-8")
    selection_before = (reports_dir / "metrics.json").read_text(encoding="utf-8")

    run_evaluation(
        config,
        processed_dir=processed_dir,
        models_dir=models_dir,
        reports_dir=reports_dir,
    )

    assert (models_dir / METADATA_FILE).read_text(encoding="utf-8") == metadata_before
    assert (reports_dir / "metrics.json").read_text(encoding="utf-8") == selection_before


def test_evaluation_refuses_a_model_that_does_not_match_the_frozen_hash(
    tmp_path, config, processed_dir, frozen
):
    models_dir, reports_dir = frozen
    model_path = models_dir / MODEL_FILE
    model_path.write_bytes(model_path.read_bytes() + b"\0")

    with pytest.raises(ValueError, match="hash mismatch"):
        run_evaluation(
            config,
            processed_dir=processed_dir,
            models_dir=models_dir,
            reports_dir=reports_dir,
        )


def test_evaluation_requires_the_frozen_artifact(tmp_path, config, processed_dir):
    with pytest.raises(FileNotFoundError):
        run_evaluation(
            config,
            processed_dir=processed_dir,
            models_dir=tmp_path / "missing-models",
            reports_dir=tmp_path / "reports",
        )


def test_evaluation_blocks_an_invalid_test_batch(tmp_path, config, processed_dir, frozen):
    models_dir, reports_dir = frozen
    invalid = pd.read_csv(processed_dir / "test.csv")
    invalid.loc[invalid.index[0], "AGE"] = 5
    invalid.to_csv(processed_dir / "test.csv", index=False)

    with pytest.raises(ContractViolation):
        run_evaluation(
            config,
            processed_dir=processed_dir,
            models_dir=models_dir,
            reports_dir=reports_dir,
        )


def test_evaluation_is_reproducible(tmp_path, config, processed_dir, frozen):
    models_dir, reports_dir = frozen
    first = run_evaluation(
        config, processed_dir=processed_dir, models_dir=models_dir, reports_dir=reports_dir
    )
    second = run_evaluation(
        config, processed_dir=processed_dir, models_dir=models_dir, reports_dir=reports_dir
    )
    assert first == second
