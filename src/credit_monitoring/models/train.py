"""Train, compare and freeze the baseline and candidate credit default models.

This is the **selection** stage. It fits both candidates on the training split, compares
them on the validation split and freezes the winner. It never reads the test split: the
final evaluation lives in :mod:`credit_monitoring.models.evaluate` and runs as its own
stage.

Rules enforced here:

- the data contract is validated **before** any estimator is fitted; a violated contract
  aborts the run and the model is never fitted;
- the scaler and the classifier are fitted on the training split only;
- selection uses the highest validation ROC-AUC over **unrounded** metrics, and a tie
  explicitly favours the baseline;
- the serialized artifact is reloaded and compared against the in-memory model within a
  declared numerical tolerance;
- every candidate is serialized under ``models/candidates/``, so the comparison is auditable
  from artifacts without retraining; only the selected model is the entry point of the
  evaluation stage, and no candidate is ever evaluated on the test split.
"""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.exceptions import ConvergenceWarning  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from credit_monitoring.config import feature_columns, load_config  # noqa: E402
from credit_monitoring.contracts import CONTRACT_VERSION, validate_batch  # noqa: E402
from credit_monitoring.data.loading import file_sha256  # noqa: E402
from credit_monitoring.paths import FIGURES_DIR, MODELS_DIR, PROCESSED_DATA_DIR, REPORTS_DIR  # noqa: E402

MODEL_FILE = "credit_model.joblib"
METADATA_FILE = "credit_model_metadata.json"
METRICS_FILE = "metrics.json"
RESOURCES_FILE = "run_resources.json"
CANDIDATES_DIR = "candidates"
DEFAULT_FIGURES_DIR = FIGURES_DIR / "model"
THRESHOLD = 0.5
RELOAD_TOLERANCE = 1e-12
ROUNDING = 6


def build_models(config: dict[str, Any]) -> dict[str, Pipeline]:
    seed = config["project"]["random_seed"]
    modeling = config["modeling"]
    builders = {
        "logistic_regression": lambda params: Pipeline(
            [
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(random_state=seed, **params)),
            ]
        ),
        "random_forest": lambda params: Pipeline(
            [("classifier", RandomForestClassifier(random_state=seed, **params))]
        ),
    }
    unknown = [name for name in modeling["candidates"] if name not in builders]
    if unknown:
        raise ValueError(f"Unknown model candidates: {unknown}")
    return {name: builders[name](modeling[name]) for name in modeling["candidates"]}


def evaluate(model: Pipeline, features: pd.DataFrame, target: pd.Series) -> dict[str, Any]:
    """Metrics on the given split. Values are returned unrounded: the selection rule
    must not depend on the rounding used for reporting."""
    probability = model.predict_proba(features)[:, 1]
    predicted = (probability >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(target, predicted, labels=[0, 1]).ravel()
    return {
        "roc_auc": float(roc_auc_score(target, probability)),
        "precision": float(precision_score(target, predicted, zero_division=0)),
        "recall": float(recall_score(target, predicted, zero_division=0)),
        "f1": float(f1_score(target, predicted, zero_division=0)),
        "accuracy": float(accuracy_score(target, predicted)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def round_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Presentation-only rounding; never used for the selection decision."""
    rounded: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, dict):
            rounded[key] = value
        elif isinstance(value, float):
            rounded[key] = round(value, ROUNDING)
        else:
            rounded[key] = value
    return rounded


def select_best(
    validation: dict[str, dict[str, Any]],
    metric: str,
    *,
    baseline: str = "logistic_regression",
    priority: tuple[str, ...] = (),
) -> str:
    """Highest validation metric wins; a tie explicitly favours the baseline.

    The decision uses the unrounded metrics. When the tie is not resolved by the
    baseline, the configured candidate order breaks it, so the result never depends on
    the incidental order of a dictionary.
    """
    if not validation:
        raise ValueError("No validation metrics to select from")
    scores = {name: float(metrics[metric]) for name, metrics in validation.items()}
    best_score = max(scores.values())
    tied = sorted(name for name, score in scores.items() if score == best_score)
    if baseline in tied:
        return baseline
    for name in priority:
        if name in tied:
            return name
    return tied[0]


def _rss_mib() -> float | None:
    """Resident set size of this process in MiB (Linux only)."""
    try:
        with open("/proc/self/statm", encoding="utf-8") as handle:
            pages = int(handle.read().split()[1])
    except (OSError, IndexError, ValueError):
        return None
    return round(pages * resource.getpagesize() / (1024 * 1024), 3)


def measure_resources(action):
    """Run ``action`` and report the local resource cost of the call."""
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    rss_before = _rss_mib()
    result = action()
    rss_after = _rss_mib()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return result, {
        "wall_time_s": round(time.perf_counter() - wall_start, 3),
        "cpu_time_s": round(time.process_time() - cpu_start, 3),
        "rss_before_mib": rss_before,
        "rss_after_mib": rss_after,
        "rss_delta_mib": (
            None if rss_before is None or rss_after is None else round(rss_after - rss_before, 3)
        ),
        "process_peak_rss_mib": round(usage.ru_maxrss / 1024, 1),
        "method": "time.perf_counter, time.process_time and /proc/self/statm",
        "platform": platform.platform(),
    }


def _fit_with_convergence(model: Pipeline, x_train: pd.DataFrame, y_train: pd.Series):
    """Fit and report whether the estimator converged."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(x_train, y_train)
    convergence = [
        str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)
    ]
    return model, {"converged": not convergence, "convergence_warnings": convergence}


def _load_split(processed_dir: Path, name: str, config: dict[str, Any]):
    frame = pd.read_csv(processed_dir / f"{name}.csv")
    return frame[feature_columns(config)], frame[config["dataset"]["canonical_target"]]


def _config_fingerprint(config: dict[str, Any]) -> str:
    relevant = {
        "random_seed": config["project"]["random_seed"],
        "features": feature_columns(config),
        "modeling": config["modeling"],
        "contract": config["contract"],
    }
    payload = json.dumps(relevant, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    sha = result.stdout.strip()
    return sha or "unknown"


def _plot_roc(models, features, target, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    for name, model in models.items():
        RocCurveDisplay.from_estimator(model, features, target, name=name, ax=ax)
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey")
    ax.set_title("Curva ROC - validacao")
    fig.savefig(figures_dir / "01_roc_validation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_confusion(model, features, target, name: str, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay.from_estimator(model, features, target, ax=ax, colorbar=False)
    ax.set_title(f"Matriz de confusao - validacao ({name})")
    fig.savefig(figures_dir / "02_confusion_matrix_validation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_training(
    config: dict[str, Any],
    *,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    models_dir: str | Path = MODELS_DIR,
    reports_dir: str | Path = REPORTS_DIR,
    figures_dir: str | Path = DEFAULT_FIGURES_DIR,
) -> dict[str, Any]:
    """Fit both candidates, compare them on validation and freeze the selected model."""
    processed_dir = Path(processed_dir)
    models_dir = Path(models_dir)
    reports_dir = Path(reports_dir)
    figures_dir = Path(figures_dir)
    for directory in (models_dir, reports_dir, figures_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # The contract gates the data before any estimator exists.
    train_frame = validate_batch(pd.read_csv(processed_dir / "train.csv"), config, labeled=True)
    validation_frame = validate_batch(
        pd.read_csv(processed_dir / "validation.csv"), config, labeled=True
    )
    features = feature_columns(config)
    target_column = config["dataset"]["canonical_target"]
    x_train = train_frame[features]
    y_train = train_frame[target_column]
    x_val = validation_frame[features]
    y_val = validation_frame[target_column]

    models = build_models(config)
    validation: dict[str, dict[str, Any]] = {}
    fit_info: dict[str, dict[str, Any]] = {}
    resources: dict[str, dict[str, Any]] = {}
    for name, model in models.items():
        (fitted, convergence), cost = measure_resources(
            lambda model=model: _fit_with_convergence(model, x_train, y_train)
        )
        models[name] = fitted
        fit_info[name] = convergence
        resources[name] = cost

    for name, model in models.items():
        validation[name] = evaluate(model, x_val, y_val)

    metric = config["modeling"]["primary_metric"]
    baseline = config["modeling"].get("baseline", "logistic_regression")
    priority = tuple(config["modeling"]["candidates"])
    best_name = select_best(validation, metric, baseline=baseline, priority=priority)
    best_model = models[best_name]

    _plot_roc(models, x_val, y_val, figures_dir)
    _plot_confusion(best_model, x_val, y_val, best_name, figures_dir)

    model_path = models_dir / MODEL_FILE
    joblib.dump(best_model, model_path)

    # Every candidate is serialized, not only the winner: the comparison must be
    # auditable from artifacts, without retraining. The frozen artifact above
    # stays the single entry point of the evaluation stage.
    candidates_dir = models_dir / CANDIDATES_DIR
    candidates_dir.mkdir(parents=True, exist_ok=True)
    candidates: dict[str, dict[str, Any]] = {}
    for name, model in models.items():
        candidate_path = candidates_dir / f"credit_model_{name}.joblib"
        joblib.dump(model, candidate_path)
        candidates[name] = {
            "path": f"{CANDIDATES_DIR}/{candidate_path.name}",
            "sha256": file_sha256(candidate_path),
            "selected": name == best_name,
            "hyperparameters": config["modeling"][name],
            "converged": fit_info[name]["converged"],
        }

    # The serialized artifact must reproduce the in-memory model.
    reloaded = joblib.load(model_path)
    before = best_model.predict_proba(x_val)[:, 1]
    after = reloaded.predict_proba(x_val)[:, 1]
    max_difference = float(abs(before - after).max())
    reload_check = {
        "tolerance": RELOAD_TOLERANCE,
        # Rounded to the tolerance precision: the parallel prediction of the forest
        # accumulates in a non-deterministic order, so the raw float difference varies
        # between runs while staying far below the tolerance.
        "max_abs_probability_difference": round(max_difference, 12),
        "passed": bool(max_difference <= RELOAD_TOLERANCE),
    }
    if not reload_check["passed"]:
        raise RuntimeError(
            f"Reloaded model differs from the fitted one: {max_difference} > {RELOAD_TOLERANCE}"
        )

    metrics = {
        "primary_metric": metric,
        "selected_model": best_name,
        "threshold": THRESHOLD,
        "contract_version": CONTRACT_VERSION,
        "validation": {name: round_metrics(values) for name, values in validation.items()},
        "selection": {
            "rule": "highest_validation_metric_with_baseline_tie_break",
            "metric": metric,
            "baseline": baseline,
            "tie_break": config["modeling"].get("tie_break", "baseline"),
            "rounded_metrics_used_for_decision": False,
            "scores": {name: values[metric] for name, values in validation.items()},
        },
        "fit": fit_info,
        "reload_check": reload_check,
    }
    (reports_dir / METRICS_FILE).write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    metadata = {
        "selected_model": best_name,
        "selection_rationale": (
            f"Maior {metric} na validacao entre {list(models)}; empate favorece o baseline "
            f"{baseline}. O conjunto de teste nao participa da selecao."
        ),
        "features": features,
        "hyperparameters": config["modeling"][best_name],
        "candidates": candidates,
        "random_seed": config["project"]["random_seed"],
        "threshold": THRESHOLD,
        "config_sha256": _config_fingerprint(config),
        "train_sha256": file_sha256(processed_dir / "train.csv"),
        "validation_sha256": file_sha256(processed_dir / "validation.csv"),
        "model_sha256": file_sha256(model_path),
        "git_sha": _git_sha(),
        "contract_version": CONTRACT_VERSION,
        "selection": metrics["selection"],
        "validation": metrics["validation"],
        "reload_check": reload_check,
        "versions": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "test_exposure": {
            "declared": True,
            "statement": (
                "O EDA historico calculou correlacoes feature-alvo e taxa de default por "
                "grupo sobre as 30.000 linhas do bruto, incluindo as linhas do conjunto de "
                "teste. A avaliacao final e uma reavaliacao sob protocolo congelado, nao "
                "uma avaliacao intocada. Ver docs/evidence/fase-1.md, secao 1.2."
            ),
            "reference": "docs/evidence/fase-1.md#12-aquisicao-e-auditoria-do-dataset",
        },
    }
    (models_dir / METADATA_FILE).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Resource measurements are not reproducible by nature, so they live outside the
    # DVC-tracked artifacts: a versioned artifact must keep the same hash on a re-run.
    (reports_dir / RESOURCES_FILE).write_text(
        json.dumps(
            {
                "note": (
                    "Medicoes locais de execucao. Nao sao versionadas pelo DVC porque "
                    "variam a cada execucao; a fase 3 as registra no MLflow."
                ),
                "per_model": resources,
                "selected_model": best_name,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Treina LR e RF, compara na validacao e congela o modelo selecionado."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--figures-dir", default=str(DEFAULT_FIGURES_DIR))
    args = parser.parse_args(argv)

    metrics = run_training(
        load_config(args.config),
        processed_dir=args.processed_dir,
        models_dir=args.models_dir,
        reports_dir=args.reports_dir,
        figures_dir=args.figures_dir,
    )
    print(
        f"Modelo selecionado: {metrics['selected_model']} "
        f"(validacao {metrics['primary_metric']}="
        f"{metrics['validation'][metrics['selected_model']][metrics['primary_metric']]:.4f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
