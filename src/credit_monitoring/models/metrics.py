"""Shared metric helpers for the selection, optimization and evaluation stages.

The helpers live in their own module so that the selection stage
(:mod:`credit_monitoring.models.train`), the optimization campaign
(:mod:`credit_monitoring.models.tune`) and the promotion decision
(:mod:`credit_monitoring.models.promotion`) compute the numbers with exactly the
same code, without importing each other.

Two rules are enforced here:

- the metrics are returned **unrounded**: the selection rule must not depend on
  the rounding used for reporting;
- the classification threshold is fixed at 0.5. Changing it can move F1,
  precision and recall, but it never improves the ROC-AUC of the same
  probabilities, so the threshold is not a tuning knob of this project.
"""

import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

THRESHOLD = 0.5
RELOAD_TOLERANCE = 1e-12
ROUNDING = 6


def evaluate(
    model: Any, features: pd.DataFrame, target: pd.Series, *, threshold: float = THRESHOLD
) -> dict[str, Any]:
    """Metrics on the given split, returned unrounded."""
    probability = model.predict_proba(features)[:, 1]
    predicted = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(target, predicted, labels=[0, 1]).ravel()
    return {
        "roc_auc": float(roc_auc_score(target, probability)),
        "average_precision": float(average_precision_score(target, probability)),
        "precision": float(precision_score(target, predicted, zero_division=0)),
        "recall": float(recall_score(target, predicted, zero_division=0)),
        "f1": float(f1_score(target, predicted, zero_division=0)),
        "accuracy": float(accuracy_score(target, predicted)),
        "brier": float(brier_score_loss(target, probability)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def round_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Presentation-only rounding; never used for a decision."""
    rounded: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, dict):
            rounded[key] = value
        elif isinstance(value, float):
            rounded[key] = round(value, ROUNDING)
        elif isinstance(value, (np.floating, np.integer)):
            rounded[key] = value.item()
        else:
            rounded[key] = value
    return rounded


def fit_with_convergence(model: Any, x_train: pd.DataFrame, y_train: pd.Series):
    """Fit an estimator and report whether it converged."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(x_train, y_train)
    convergence = [
        str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)
    ]
    return model, {"converged": not convergence, "convergence_warnings": convergence}
