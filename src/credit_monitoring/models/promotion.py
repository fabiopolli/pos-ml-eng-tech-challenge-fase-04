"""Final validation round and promotion decision of the optimization campaign.

This module implements the executable package **1.6-O4** of plan 1.6: the single,
pre-specified validation round that compares the two frozen finalists against the
Random Forest that is currently published.

Rules implemented here, exactly as written in the plan:

- the comparison is a **single** round: the incumbent and the two finalists are
  scored on the same validation rows, with the probabilities aligned by ID;
- the primary metric is the ROC-AUC of the probabilities of the positive class
  (``1``), computed without rounding;
- a finalist is promoted only when it satisfies **all** of:

  1. ``ROC-AUC_validation(finalist) - ROC-AUC_validation(incumbent) >= 0.010``;
  2. it beats the control of the same family by at least ``0.005`` of mean
     cross-validated ROC-AUC, on the same five folds;
  3. the lower bound of the paired bootstrap interval of the difference is ``> 0``;
  4. for the Random Forest, the repetition seeds also beat the control
     (instability blocks the promotion);
  5. the integrity checks (contract, no leakage, reload, traceability) pass;

- between eligible finalists the highest validation ROC-AUC wins; an exact tie
  favours the Logistic Regression;
- if no finalist satisfies every criterion, the current Random Forest is kept and
  the result is recorded as an **insufficient or inconclusive gain**.

The bootstrap is paired and stratified by the target: every replica draws, with
replacement, the same indices for every model, preserving the number of positives
and negatives. The interval is a percentile interval of 97.5% per comparison
(quantiles 1.25% and 98.75%), which is the Bonferroni adjustment of the two
pre-defined contrasts for a nominal family-wise level of 95%.

The interval is conditional to the fitted models and to this validation split. It
does not incorporate the whole search process and it does not correct the
historical exposure of the validation split.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from credit_monitoring.models.metrics import evaluate, round_metrics

COMPARISON_SCHEMA_VERSION = "1.0.0"


def stratified_bootstrap_indices(
    target: np.ndarray, n_resamples: int, seed: int
) -> list[np.ndarray]:
    """Indices of the paired, stratified bootstrap replicas.

    The same replica is used by every model, so the difference of the ROC-AUC is
    estimated on identical resamples. The number of positives and negatives is
    preserved in every replica.
    """
    rng = np.random.default_rng(seed)
    positives = np.flatnonzero(target == 1)
    negatives = np.flatnonzero(target == 0)
    if len(positives) == 0 or len(negatives) == 0:
        raise ValueError("The bootstrap needs both classes in the validation split")
    replicas: list[np.ndarray] = []
    for _ in range(n_resamples):
        drawn = np.concatenate(
            [
                rng.choice(positives, size=len(positives), replace=True),
                rng.choice(negatives, size=len(negatives), replace=True),
            ]
        )
        replicas.append(drawn)
    return replicas


def bootstrap_paired_delta(
    target: np.ndarray,
    incumbent: np.ndarray,
    candidate: np.ndarray,
    *,
    n_resamples: int,
    seed: int,
    ci_level: float,
) -> dict[str, Any]:
    """Paired bootstrap of ``ROC-AUC(candidate) - ROC-AUC(incumbent)``."""
    if len(incumbent) != len(candidate) or len(incumbent) != len(target):
        raise ValueError("The probabilities and the target must be aligned")
    replicas = stratified_bootstrap_indices(target, n_resamples, seed)
    incumbent_scores = np.empty(n_resamples, dtype=float)
    candidate_scores = np.empty(n_resamples, dtype=float)
    for index, rows in enumerate(replicas):
        incumbent_scores[index] = roc_auc_score(target[rows], incumbent[rows])
        candidate_scores[index] = roc_auc_score(target[rows], candidate[rows])
    deltas = candidate_scores - incumbent_scores
    alpha = (1.0 - ci_level) / 2.0
    low, high = np.quantile(deltas, [alpha, 1.0 - alpha])
    return {
        "metric": "roc_auc",
        "delta": float(roc_auc_score(target, candidate) - roc_auc_score(target, incumbent)),
        "ci_low": float(low),
        "ci_high": float(high),
        "level": ci_level,
        "quantiles": [alpha, 1.0 - alpha],
        "n_resamples": n_resamples,
        "seed": seed,
        "method": "paired stratified percentile bootstrap",
        "incumbent_mean_in_replicas": float(incumbent_scores.mean()),
        "candidate_mean_in_replicas": float(candidate_scores.mean()),
        "replicas_with_positive_delta": int((deltas > 0).sum()),
    }


def _criterion(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"criterion": name, "passed": bool(passed), "detail": detail}


def evaluate_criteria(
    candidate: dict[str, Any],
    incumbent: dict[str, Any],
    criteria_config: dict[str, Any],
    *,
    cv_evidence: dict[str, Any] | None = None,
    stability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the pre-declared promotion criteria to one candidate."""
    min_gain = float(criteria_config["min_gain_validation"])
    min_cv_gain = float(criteria_config["min_gain_cv_mean"])
    gain = candidate["metrics"]["roc_auc"] - incumbent["metrics"]["roc_auc"]

    checks = [
        _criterion(
            "validation_gain_at_least_min_gain",
            gain >= min_gain,
            f"delta={gain!r} against the required {min_gain!r}",
        )
    ]

    cv_gain = None
    if cv_evidence is not None:
        cv_gain = cv_evidence.get("cv_gain_over_control")
        checks.append(
            _criterion(
                "cross_validation_gain_over_same_family_control",
                cv_gain is not None and cv_gain >= min_cv_gain,
                f"cv_gain={cv_gain!r} against the required {min_cv_gain!r}",
            )
        )

    contrast = candidate.get("contrast")
    if contrast is not None:
        checks.append(
            _criterion(
                "paired_bootstrap_lower_bound_above_zero",
                contrast["ci_low"] > 0,
                f"ci_low={contrast['ci_low']!r}, ci_high={contrast['ci_high']!r}",
            )
        )

    if stability is not None:
        checks.append(
            _criterion(
                "random_forest_repetitions_beat_control",
                bool(stability.get("repetitions_beat_control")),
                (
                    f"repetition mean={stability.get('repetition_mean_roc_auc')!r} against "
                    f"control mean={stability.get('control_mean_roc_auc')!r}"
                ),
            )
        )

    checks.append(
        _criterion(
            "integrity_checks",
            bool(candidate.get("integrity", {}).get("passed", False)),
            candidate.get("integrity", {}).get("detail", "integrity checks not reported"),
        )
    )

    return {
        "candidate": candidate["key"],
        "validation_gain": gain,
        "cv_gain_over_control": cv_gain,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
    }


def run_final_comparison(
    config: dict[str, Any],
    optimization: dict[str, Any],
    *,
    target: pd.Series,
    probabilities: dict[str, np.ndarray],
    models: dict[str, dict[str, Any]],
    incumbent_key: str,
    cv_evidence: dict[str, dict[str, Any]],
    stability: dict[str, Any] | None = None,
    validation_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the single validation round and decide whether a finalist is promoted.

    ``models`` describes each participant of the round: ``key``, ``role``
    (``incumbent`` or ``finalist``), ``algorithm``, ``version``, ``sha256`` and
    the optional ``integrity`` block. ``probabilities`` holds the aligned
    probabilities of the positive class.
    """
    criteria_config = optimization["criteria"]
    target_array = np.asarray(target)
    scored: dict[str, dict[str, Any]] = {}
    for key, description in models.items():
        probability = np.asarray(probabilities[key], dtype=float)
        if len(probability) != len(target_array):
            raise ValueError(f"Probability length mismatch for '{key}'")
        metrics = evaluate(
            _ProbabilitiesOnly(probability),
            None,
            target,
            threshold=float(optimization["threshold"]),
        )
        scored[key] = {**description, "metrics": metrics}

    incumbent = scored[incumbent_key]
    for key, entry in scored.items():
        if key == incumbent_key:
            continue
        integrity = (cv_evidence.get(key) or {}).get("integrity")
        if integrity is not None:
            entry["integrity"] = integrity
    contrasts: dict[str, dict[str, Any]] = {}
    for key in scored:
        if key == incumbent_key:
            continue
        contrasts[key] = bootstrap_paired_delta(
            target_array,
            np.asarray(probabilities[incumbent_key], dtype=float),
            np.asarray(probabilities[key], dtype=float),
            n_resamples=int(criteria_config["bootstrap_resamples"]),
            seed=int(criteria_config["bootstrap_seed"]),
            ci_level=float(criteria_config["ci_level"]),
        )
        scored[key]["contrast"] = contrasts[key]

    criterion_results = {
        key: evaluate_criteria(
            scored[key],
            incumbent,
            criteria_config,
            cv_evidence=cv_evidence.get(key),
            stability=stability if "random_forest" in key else None,
        )
        for key in scored
        if key != incumbent_key
    }

    eligible = [key for key, result in criterion_results.items() if result["passed"]]
    decision: dict[str, Any]
    if eligible:
        # Highest validation ROC-AUC wins; an exact tie favours the Logistic
        # Regression, the simpler model.
        def _rank(key: str) -> tuple[float, int]:
            preference = 0 if key == "logistic_regression_finalist" else 1
            return (-scored[key]["metrics"]["roc_auc"], preference)

        best = sorted(eligible, key=_rank)[0]
        decision = {
            "action": "promote",
            "selected": best,
            "reason": (
                "O finalista satisfaz todos os criterios pre-declarados e tem o maior "
                "ROC-AUC de validacao entre os finalistas elegiveis."
            ),
            "kept_current": False,
        }
    else:
        decision = {
            "action": "keep_current",
            "selected": incumbent_key,
            "reason": (
                "Nenhum finalista satisfaz todos os criterios: ganho insuficiente ou "
                "inconclusivo. O RF vigente e mantido."
            ),
            "kept_current": True,
        }

    payload = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "experiment_id": optimization["experiment_id"],
        "protocol_version": optimization["protocol_version"],
        "state": "frozen_decision",
        "primary_metric": optimization.get("primary_metric", "roc_auc"),
        "threshold": float(optimization["threshold"]),
        "incumbent": incumbent_key,
        "validation": {
            "rows": int(len(target_array)),
            "positives": int((target_array == 1).sum()),
            "sha256": validation_sha256,
        },
        "models": {
            key: {
                **{
                    field: value
                    for field, value in entry.items()
                    if field not in {"metrics", "contrast"}
                },
                "metrics": round_metrics(entry["metrics"]),
                "metrics_unrounded": entry["metrics"],
                "contrast": entry.get("contrast"),
            }
            for key, entry in scored.items()
        },
        "criteria": criterion_results,
        "criteria_config": criteria_config,
        "decision": decision,
        "interpretation_limits": [
            "O intervalo e condicional aos modelos ajustados e a esta validacao.",
            "O intervalo nao incorpora todo o processo de busca nem corrige a exposicao "
            "historica da validacao.",
            "O desvio-padrao dos cinco folds nao e um intervalo de confianca.",
            "Um intervalo positivo nao e prova de generalizacao nem de adequacao ao credito real.",
        ],
    }
    return payload


class _ProbabilitiesOnly:
    """Adapter that exposes ``predict_proba`` for already computed probabilities."""

    def __init__(self, probability: np.ndarray) -> None:
        self._probability = probability

    def predict_proba(self, _features: Any = None) -> np.ndarray:
        return np.column_stack([1.0 - self._probability, self._probability])


def write_comparison(payload: dict[str, Any], path: str | Path) -> Path:
    """Write the frozen comparison report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def comparison_fingerprint(payload: dict[str, Any]) -> str:
    """Stable hash of the decision, used to bind the artifacts to the report."""
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()
