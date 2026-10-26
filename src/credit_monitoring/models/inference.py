"""Shared local inference service for the frozen pipelines.

The model laboratory of the dashboard (plan 1.6, package ``1.6-O6``) and the future
inference stage of phase 2 share this module, so the contract rules, the feature
selection, the threshold and the probability semantics live in **one** place and
are never duplicated inside the widgets.

Rules enforced here:

- the whole batch is validated against the data contract **before** any model is
  called; an invalid batch is rejected as a whole and produces **zero** calls to any
  selected model;
- the model receives the 19 financial inputs in the order of the manifest; the
  optional ratio features are produced inside the frozen pipeline, never by the
  caller;
- only ``predict_proba`` of a frozen pipeline is used, and the reported number is
  the probability of the positive class (``1``). Nothing here claims that the
  probabilities are calibrated.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from credit_monitoring.config import feature_columns
from credit_monitoring.contracts import validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.models.metrics import THRESHOLD


class ModelArtifactError(RuntimeError):
    """Raised when an artifact is missing, unreadable or does not match its hash."""


@dataclass(frozen=True)
class InferenceResult:
    """Outcome of one inference call over a validated batch."""

    rows: int
    probability: np.ndarray
    predicted: np.ndarray
    threshold: float
    duration_s: float
    model_sha256: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "threshold": self.threshold,
            "duration_s": round(self.duration_s, 6),
            "model_sha256": self.model_sha256,
            "mean_probability": float(self.probability.mean()),
            "predicted_positives": int(self.predicted.sum()),
        }


def load_model(path: str | Path, *, expected_sha256: str | None = None) -> Any:
    """Load a frozen pipeline, refusing an artifact that does not match its hash."""
    path = Path(path)
    if not path.is_file():
        raise ModelArtifactError(f"Model artifact not found: {path}")
    digest = file_sha256(path)
    if expected_sha256 and digest != expected_sha256:
        raise ModelArtifactError(f"Model artifact hash mismatch: {digest} != {expected_sha256}")
    return joblib.load(path)


def select_model_features(
    frame: pd.DataFrame, config: dict[str, Any], features: list[str] | None = None
) -> pd.DataFrame:
    """Select the model inputs, in the order declared by the manifest."""
    selected = list(features or feature_columns(config))
    missing = [column for column in selected if column not in frame.columns]
    if missing:
        raise ModelArtifactError(f"Missing model inputs: {missing}")
    return frame[selected]


def infer_batch(
    model: Any,
    frame: pd.DataFrame,
    config: dict[str, Any],
    *,
    features: list[str] | None = None,
    threshold: float = THRESHOLD,
    model_sha256: str | None = None,
) -> InferenceResult:
    """Validate the batch and score it with one frozen pipeline."""
    validated = validate_batch(frame, config, labeled=False)
    inputs = select_model_features(validated, config, features)
    start = time.perf_counter()
    probability = np.asarray(model.predict_proba(inputs)[:, 1], dtype=float)
    duration = time.perf_counter() - start
    return InferenceResult(
        rows=len(inputs),
        probability=probability,
        predicted=(probability >= threshold).astype(int),
        threshold=threshold,
        duration_s=duration,
        model_sha256=model_sha256,
    )


def compare_models(
    models: dict[str, Any],
    frame: pd.DataFrame,
    config: dict[str, Any],
    *,
    features: list[str] | None = None,
    threshold: float = THRESHOLD,
) -> dict[str, Any]:
    """Score the same validated batch with every selected model.

    The batch is validated once, **before** the first call. When the contract is
    violated the exception propagates and no model is called at all.
    """
    validated = validate_batch(frame, config, labeled=False)
    inputs = select_model_features(validated, config, features)
    results: dict[str, InferenceResult] = {}
    for key, model in models.items():
        start = time.perf_counter()
        probability = np.asarray(model.predict_proba(inputs)[:, 1], dtype=float)
        duration = time.perf_counter() - start
        results[key] = InferenceResult(
            rows=len(inputs),
            probability=probability,
            predicted=(probability >= threshold).astype(int),
            threshold=threshold,
            duration_s=duration,
        )
    return {
        "rows": len(inputs),
        "threshold": threshold,
        "results": results,
        "probabilities": {key: value.probability for key, value in results.items()},
        "predictions": {key: value.predicted for key, value in results.items()},
    }


def divergence_summary(comparison: dict[str, Any], tolerance: float = 1e-12) -> dict[str, Any]:
    """Report where the selected models disagree, and by how much."""
    probabilities = comparison["probabilities"]
    keys = list(probabilities)
    if len(keys) < 2:
        return {"pairs": [], "max_abs_difference": 0.0, "rows_with_divergence": 0}
    pairs: list[dict[str, Any]] = []
    max_difference = 0.0
    diverging_rows = 0
    for index, left in enumerate(keys):
        for right in keys[index + 1 :]:
            difference = np.abs(probabilities[left] - probabilities[right])
            max_difference = max(max_difference, float(difference.max()))
            diverging_rows = int((difference > tolerance).sum())
            pairs.append(
                {
                    "models": [left, right],
                    "max_abs_difference": float(difference.max()),
                    "rows_with_divergence": diverging_rows,
                    "class_disagreements": int(
                        (comparison["predictions"][left] != comparison["predictions"][right]).sum()
                    ),
                }
            )
    return {
        "pairs": pairs,
        "max_abs_difference": max_difference,
        "rows_with_divergence": diverging_rows,
        "tolerance": tolerance,
    }
