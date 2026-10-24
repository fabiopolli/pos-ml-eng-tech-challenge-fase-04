"""Train, compare and serialize the baseline and candidate credit default models."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
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
from credit_monitoring.data.loading import file_sha256  # noqa: E402
from credit_monitoring.paths import FIGURES_DIR, MODELS_DIR, PROCESSED_DATA_DIR, REPORTS_DIR  # noqa: E402

MODEL_FILE = "credit_model.joblib"
METADATA_FILE = "credit_model_metadata.json"
METRICS_FILE = "metrics.json"
DEFAULT_FIGURES_DIR = FIGURES_DIR / "model"
THRESHOLD = 0.5


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
    probability = model.predict_proba(features)[:, 1]
    predicted = (probability >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(target, predicted, labels=[0, 1]).ravel()
    return {
        "roc_auc": round(float(roc_auc_score(target, probability)), 6),
        "precision": round(float(precision_score(target, predicted, zero_division=0)), 6),
        "recall": round(float(recall_score(target, predicted, zero_division=0)), 6),
        "f1": round(float(f1_score(target, predicted, zero_division=0)), 6),
        "accuracy": round(float(accuracy_score(target, predicted)), 6),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def select_best(validation: dict[str, dict[str, Any]], metric: str) -> str:
    """Highest validation metric wins; ties keep the earlier candidate (the baseline)."""
    return max(validation, key=lambda name: validation[name][metric])


def _load_split(processed_dir: Path, name: str, config: dict[str, Any]):
    frame = pd.read_csv(processed_dir / f"{name}.csv")
    return frame[feature_columns(config)], frame[config["dataset"]["canonical_target"]]


def _config_fingerprint(config: dict[str, Any]) -> str:
    relevant = {
        "random_seed": config["project"]["random_seed"],
        "features": feature_columns(config),
        "modeling": config["modeling"],
    }
    payload = json.dumps(relevant, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _plot_roc(models, features, target, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    for name, model in models.items():
        RocCurveDisplay.from_estimator(model, features, target, name=name, ax=ax)
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey")
    ax.set_title("Curva ROC - validação")
    fig.savefig(figures_dir / "01_roc_validation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_confusion(model, features, target, name: str, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay.from_estimator(model, features, target, ax=ax, colorbar=False)
    ax.set_title(f"Matriz de confusão - teste ({name})")
    fig.savefig(figures_dir / "02_confusion_matrix_test.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_training(
    config: dict[str, Any],
    *,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    models_dir: str | Path = MODELS_DIR,
    reports_dir: str | Path = REPORTS_DIR,
    figures_dir: str | Path = DEFAULT_FIGURES_DIR,
) -> dict[str, Any]:
    processed_dir = Path(processed_dir)
    models_dir = Path(models_dir)
    reports_dir = Path(reports_dir)
    figures_dir = Path(figures_dir)
    for directory in (models_dir, reports_dir, figures_dir):
        directory.mkdir(parents=True, exist_ok=True)

    x_train, y_train = _load_split(processed_dir, "train", config)
    x_val, y_val = _load_split(processed_dir, "validation", config)
    x_test, y_test = _load_split(processed_dir, "test", config)

    models = build_models(config)
    for model in models.values():
        model.fit(x_train, y_train)
    validation = {name: evaluate(model, x_val, y_val) for name, model in models.items()}

    metric = config["modeling"]["primary_metric"]
    best_name = select_best(validation, metric)
    best_model = models[best_name]
    # The test split is scored only for the selected model.
    test = evaluate(best_model, x_test, y_test)

    _plot_roc(models, x_val, y_val, figures_dir)
    _plot_confusion(best_model, x_test, y_test, best_name, figures_dir)

    joblib.dump(best_model, models_dir / MODEL_FILE)
    metrics = {
        "primary_metric": metric,
        "selected_model": best_name,
        "threshold": THRESHOLD,
        "validation": validation,
        "test": test,
    }
    (reports_dir / METRICS_FILE).write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata = {
        "selected_model": best_name,
        "selection_rationale": (
            f"Maior {metric} na validação entre {list(models)}; "
            "o conjunto de teste foi usado apenas no modelo escolhido."
        ),
        "features": feature_columns(config),
        "hyperparameters": config["modeling"][best_name],
        "random_seed": config["project"]["random_seed"],
        "config_sha256": _config_fingerprint(config),
        "train_sha256": file_sha256(processed_dir / "train.csv"),
        "validation_sha256": file_sha256(processed_dir / "validation.csv"),
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__},
    }
    (models_dir / METADATA_FILE).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Treina LR e RF e serializa o melhor modelo.")
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
        f"(teste {metrics['primary_metric']}={metrics['test'][metrics['primary_metric']]:.4f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
