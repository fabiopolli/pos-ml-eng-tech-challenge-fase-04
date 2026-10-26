"""Final evaluation of the frozen model on the test split.

This is the **evaluation** stage, deliberately separate from the selection stage
(:mod:`credit_monitoring.models.train`):

- it reads the frozen artifact and its metadata, and refuses to run when the artifact
  does not match the hash recorded at selection time;
- it validates the test batch against the data contract before any prediction;
- it never touches the validation metrics and never changes the selection.

Re-running this stage reproduces the same numbers; it does not create a new independent
evaluation.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from credit_monitoring.config import feature_columns, load_config
from credit_monitoring.contracts import CONTRACT_VERSION, validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.models.train import (
    METADATA_FILE,
    MODEL_FILE,
    THRESHOLD,
    evaluate,
    round_metrics,
)
from credit_monitoring.paths import MODELS_DIR, PROCESSED_DATA_DIR, REPORTS_DIR

TEST_METRICS_FILE = "test_metrics.json"


def run_evaluation(
    config: dict[str, Any],
    *,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    models_dir: str | Path = MODELS_DIR,
    reports_dir: str | Path = REPORTS_DIR,
) -> dict[str, Any]:
    processed_dir = Path(processed_dir)
    models_dir = Path(models_dir)
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    model_path = models_dir / MODEL_FILE
    metadata_path = models_dir / METADATA_FILE
    if not model_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(
            "Frozen model not found. Run the selection stage before the evaluation stage."
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    model_sha256 = file_sha256(model_path)
    expected_sha256 = metadata.get("model_sha256")
    if expected_sha256 and model_sha256 != expected_sha256:
        raise ValueError(
            f"Frozen model hash mismatch: {model_sha256} != {expected_sha256}. "
            "The artifact does not match the frozen selection."
        )

    features = feature_columns(config)
    if metadata.get("features") != features:
        raise ValueError(
            "The frozen feature list does not match the current configuration; "
            "the selection must be redone before evaluating."
        )

    test_frame = validate_batch(pd.read_csv(processed_dir / "test.csv"), config, labeled=True)
    target_column = config["dataset"]["canonical_target"]
    model = joblib.load(model_path)
    test_metrics = evaluate(model, test_frame[features], test_frame[target_column])

    payload = {
        "selected_model": metadata["selected_model"],
        "threshold": metadata.get("threshold", THRESHOLD),
        "contract_version": metadata.get("contract_version", CONTRACT_VERSION),
        "model_sha256": model_sha256,
        "test_sha256": file_sha256(processed_dir / "test.csv"),
        "test": round_metrics(test_metrics),
        "protocol": {
            "frozen": True,
            "selection_source": "models/credit_model_metadata.json",
            "primary_metric": config["modeling"]["primary_metric"],
            "note": (
                "Avaliacao final sob protocolo congelado. Reexecutar este estagio reproduz "
                "os mesmos numeros: nao cria uma avaliacao independente nova."
            ),
        },
        "test_exposure": metadata.get("test_exposure", {}),
    }
    (reports_dir / TEST_METRICS_FILE).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avalia o modelo congelado no conjunto de teste.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    args = parser.parse_args(argv)

    payload = run_evaluation(
        load_config(args.config),
        processed_dir=args.processed_dir,
        models_dir=args.models_dir,
        reports_dir=args.reports_dir,
    )
    print(
        f"Avaliacao final: {payload['selected_model']} "
        f"(teste roc_auc={payload['test']['roc_auc']:.4f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
