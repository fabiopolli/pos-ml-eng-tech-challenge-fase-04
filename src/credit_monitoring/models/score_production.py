"""Score phase-2 batches with the frozen M1 model and persist ID associations."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from credit_monitoring.config import load_config
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.data.simulate import protocol_sha256
from credit_monitoring.models.inference import infer_batch, load_model
from credit_monitoring.paths import DATA_DIR, MODELS_DIR, REPORTS_DIR


class ProductionScoringError(ValueError):
    """Raised when phase-2 inputs or frozen M1 model metadata are inconsistent."""


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")


def _write_immutable(path: Path, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    if path.exists():
        if file_sha256(path) != digest:
            raise ProductionScoringError(
                f"Refusing to overwrite an existing prediction artifact: {path}"
            )
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return digest


def _probability_summary(probability: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    values = np.asarray(probability, dtype=float)
    if values.size == 0 or not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ProductionScoringError(
            "Model returned empty, non-finite, or out-of-range probabilities"
        )
    quantiles = np.quantile(values, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "rows": int(values.size),
        "mean": float(values.mean()),
        "std_population": float(values.std(ddof=0)),
        "min": float(values.min()),
        "p05": float(quantiles[0]),
        "p25": float(quantiles[1]),
        "median": float(quantiles[2]),
        "p75": float(quantiles[3]),
        "p95": float(quantiles[4]),
        "max": float(values.max()),
        "predicted_positives": int(np.asarray(predicted, dtype=int).sum()),
    }


def _stable_inference_summary(
    result: Any, probability: np.ndarray, predicted: np.ndarray
) -> dict[str, Any]:
    """Return reproducible metadata, excluding local paths and execution timing."""
    return {
        "rows": int(result.rows),
        "threshold": float(result.threshold),
        "model_sha256": result.model_sha256,
        "mean_probability": float(probability.mean()),
        "predicted_positives": int(predicted.sum()),
    }


def _persisted_probabilities(result: Any, decimals: int) -> tuple[np.ndarray, np.ndarray]:
    probability = np.round(result.probability, decimals=decimals)
    predicted = (probability >= result.threshold).astype(int)
    return probability, predicted


def run_scoring(
    *,
    original_path: Path,
    modified_path: Path,
    manifest_path: Path,
    model_path: Path,
    metadata_path: Path,
    original_predictions_path: Path,
    modified_predictions_path: Path,
    summary_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    drift_config = config["drift"]
    if manifest["protocol_version"] != drift_config["protocol_version"]:
        raise ProductionScoringError("Simulation manifest uses a different protocol version")
    if manifest["protocol_sha256"] != protocol_sha256(drift_config):
        raise ProductionScoringError(
            "Simulation manifest protocol hash differs from current config"
        )
    model_sha = file_sha256(model_path)
    expected_model_sha = metadata["model_sha256"]
    if model_sha != expected_model_sha:
        raise ProductionScoringError(
            f"Frozen model hash mismatch: {model_sha} != {expected_model_sha}"
        )
    if metadata["contract_version"] != "1.0.0":
        raise ProductionScoringError("Model metadata contract version is incompatible")
    if float(metadata["threshold"]) != float(config["modeling"].get("threshold", 0.5)):
        # The M1 manifest is the source of truth; project config defaults to 0.5.
        if float(metadata["threshold"]) != 0.5:
            raise ProductionScoringError("Frozen threshold differs from the phase-2 configuration")

    expected_hashes = {
        "original": manifest["batches"]["original"]["sha256"],
        "modified": manifest["batches"]["modified"]["sha256"],
    }
    paths = {"original": original_path, "modified": modified_path}
    for key, path in paths.items():
        actual_hash = file_sha256(path)
        if actual_hash != expected_hashes[key]:
            raise ProductionScoringError(
                f"{key} batch hash differs from simulation manifest: {actual_hash} != "
                f"{expected_hashes[key]}"
            )

    model = load_model(model_path, expected_sha256=expected_model_sha)
    id_column = config["dataset"]["id_column"]
    scoring_config = drift_config["scoring"]
    if scoring_config["persisted_probability_rounding"] != "half_to_even":
        raise ProductionScoringError("Unsupported persisted probability rounding rule")
    decimals = int(scoring_config["persisted_probability_decimals"])
    if not 0 <= decimals <= 15:
        raise ProductionScoringError("Persisted probability precision must be between 0 and 15")
    outputs: dict[str, Path] = {
        "original": original_predictions_path,
        "modified": modified_predictions_path,
    }
    predictions: dict[str, dict[str, Any]] = {}
    summaries: dict[str, Any] = {}
    for key, input_path in paths.items():
        frame = pd.read_csv(input_path)
        result = infer_batch(
            model,
            frame,
            config,
            threshold=float(metadata["threshold"]),
            model_sha256=model_sha,
        )
        if result.rows != len(frame) or len(result.probability) != len(frame):
            raise ProductionScoringError(f"Inference row count mismatch for {key}")
        probability, predicted = _persisted_probabilities(result, decimals)
        prediction_frame = pd.DataFrame(
            {
                "scenario_id": manifest["scenario_id"],
                id_column: frame[id_column].to_numpy(),
                "probability_default": probability,
                "predicted_default": predicted,
            }
        )
        prediction_sha = _write_immutable(outputs[key], _csv_bytes(prediction_frame))
        predictions[key] = {
            "sha256": prediction_sha,
            "summary": _probability_summary(probability, predicted),
        }
        summaries[key] = _stable_inference_summary(result, probability, predicted)

    summary = {
        "schema_version": "1.0.0",
        "scenario_id": manifest["scenario_id"],
        "protocol_version": manifest["protocol_version"],
        "contract_version": metadata["contract_version"],
        "model_sha256": model_sha,
        "threshold": float(metadata["threshold"]),
        "probability_decimals": decimals,
        "probability_rounding": scoring_config["persisted_probability_rounding"],
        "input_sha256": expected_hashes,
        "predictions": predictions,
        "inference": summaries,
        "interpretation": (
            "Predictions are associated with source IDs for traceability; no performance "
            "metric is calculated because labels are absent from production batches."
        ),
    }
    summary_bytes = (json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    _write_immutable(summary_path, summary_bytes)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    base = DATA_DIR / "production/v1.0.2"
    parser.add_argument("--original", type=Path, default=base / "original.csv")
    parser.add_argument("--modified", type=Path, default=base / "modified.csv")
    parser.add_argument("--manifest", type=Path, default=base / "manifest.json")
    parser.add_argument("--model", type=Path, default=MODELS_DIR / "credit_model.joblib")
    parser.add_argument("--metadata", type=Path, default=MODELS_DIR / "credit_model_metadata.json")
    parser.add_argument("--output-dir", type=Path, default=base / "predictions")
    parser.add_argument(
        "--summary",
        type=Path,
        default=REPORTS_DIR / "drift/prediction_summary-v1.0.2.json",
    )
    args = parser.parse_args()
    summary = run_scoring(
        original_path=args.original,
        modified_path=args.modified,
        manifest_path=args.manifest,
        model_path=args.model,
        metadata_path=args.metadata,
        original_predictions_path=args.output_dir / "original.csv",
        modified_predictions_path=args.output_dir / "modified.csv",
        summary_path=args.summary,
        config=load_config(),
    )
    print(
        json.dumps(
            {"scenario_id": summary["scenario_id"], "predictions": summary["predictions"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
