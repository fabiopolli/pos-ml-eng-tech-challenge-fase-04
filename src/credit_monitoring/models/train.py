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

**Optimization campaign mode (plan 1.6).** When an optimization protocol is supplied,
this stage also performs the single, pre-specified validation round of the campaign
(``1.6-O4``) and freezes its decision (``1.6-O5``):

- the participants of the round are the Random Forest that is currently published (the
  incumbent), the Logistic Regression control and the two finalists frozen by
  :mod:`credit_monitoring.models.tune`;
- the decision follows the pre-declared criteria of ``configs/optimization.yaml`` and is
  written to ``reports/optimization/<experiment_id>/selection/comparison.json`` **before**
  the evaluation stage runs;
- with ``keep_current`` the published artifact stays the incumbent Random Forest: the
  rejected finalist is never published under the name of the current model;
- the incumbent is archived, tracked, before the published outputs are overwritten.
"""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import time
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
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from credit_monitoring.config import feature_columns, load_config  # noqa: E402
from credit_monitoring.contracts import CONTRACT_VERSION, validate_batch  # noqa: E402
from credit_monitoring.data.loading import file_sha256  # noqa: E402
from credit_monitoring.models.features import RATIO_FEATURE_NAMES  # noqa: E402
from credit_monitoring.models.metrics import (  # noqa: E402
    RELOAD_TOLERANCE,
    THRESHOLD,
    evaluate,
    fit_with_convergence,
    round_metrics,
)
from credit_monitoring.models.promotion import (  # noqa: E402
    run_final_comparison,
    write_comparison,
)
from credit_monitoring.paths import FIGURES_DIR, MODELS_DIR, PROCESSED_DATA_DIR, REPORTS_DIR  # noqa: E402

MODEL_FILE = "credit_model.joblib"
METADATA_FILE = "credit_model_metadata.json"
METRICS_FILE = "metrics.json"
RESOURCES_FILE = "run_resources.json"
CANDIDATES_DIR = "candidates"
DEFAULT_FIGURES_DIR = FIGURES_DIR / "model"
SELECTION_DIR_NAME = "selection"
INCUMBENT_DIR_NAME = "incumbent"
COMPARISON_FILE = "comparison.json"
PREDICTIONS_FILE = "validation_predictions.csv"

# The incumbent is the Random Forest published by the previous selection: the control
# fitted in this stage has the same hyperparameters, the same seed and the same
# training rows, so it *is* the incumbent.
INCUMBENT_KEY = "random_forest"
CONTROL_KEY = "logistic_regression"
FINALIST_KEYS = {
    "logistic_regression": "logistic_regression_finalist",
    "random_forest": "random_forest_finalist",
}


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


def _load_campaign(
    optimization: dict[str, Any],
    reports_dir: Path,
    models_dir: Path,
) -> dict[str, Any]:
    """Read the frozen campaign artifacts produced by the tuning stage."""
    experiment_id = optimization["experiment_id"]
    tuning_dir = reports_dir / "optimization" / experiment_id / "tuning"
    finalists_dir = models_dir / "optimization" / experiment_id / "finalists"
    required = {
        "finalists": tuning_dir / "finalists.json",
        "manifest": tuning_dir / "manifest.json",
        "ablation": tuning_dir / "ablation.json",
        "stability": tuning_dir / "stability.json",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "The optimization campaign artifacts are missing: "
            + ", ".join(missing)
            + ". Run the tuning stage before the selection stage."
        )
    payload = {
        name: json.loads(path.read_text(encoding="utf-8")) for name, path in required.items()
    }
    payload["paths"] = {"tuning": tuning_dir, "finalists": finalists_dir}
    payload["experiment_id"] = experiment_id
    return payload


def _campaign_integrity(
    campaign: dict[str, Any],
    algorithm: str,
    train_sha256: str,
) -> dict[str, Any]:
    """Integrity checks of one finalist, recorded with the decision."""
    record = campaign["finalists"]["finalists"][algorithm]
    checks = {
        "trained_on_train_split_only": record["train_sha256"] == train_sha256,
        "artifact_present": bool(record["sha256"]),
        "converged": bool(record["converged"]),
        "hash_recorded": bool(record["sha256"]),
    }
    detail = "; ".join(f"{key}={value}" for key, value in checks.items())
    return {
        "passed": all(checks.values()),
        "detail": detail,
        "checks": checks,
        "artifact_sha256": record["sha256"],
        "train_sha256": record["train_sha256"],
    }


def _run_campaign_round(
    config: dict[str, Any],
    optimization: dict[str, Any],
    campaign: dict[str, Any],
    models: dict[str, Pipeline],
    x_val: pd.DataFrame,
    y_val: pd.Series,
    ids: np.ndarray,
    validation: dict[str, dict[str, Any]],
    *,
    models_dir: Path,
    reports_dir: Path,
    train_sha256: str,
    validation_sha256: str,
) -> tuple[dict[str, Any], str, Pipeline, dict[str, Any]]:
    """Run the single validation round of the campaign and freeze the decision."""
    experiment_id = optimization["experiment_id"]
    finalists_dir = campaign["paths"]["finalists"]
    finalists: dict[str, Pipeline] = {}
    for algorithm in FINALIST_KEYS:
        record = campaign["finalists"]["finalists"][algorithm]
        artifact = finalists_dir / Path(record["artifact"]).name
        if not artifact.is_file():
            raise FileNotFoundError(f"Finalist artifact not found: {artifact}")
        finalists[algorithm] = joblib.load(artifact)

    participants: dict[str, dict[str, Any]] = {
        INCUMBENT_KEY: {
            "key": INCUMBENT_KEY,
            "role": "incumbent",
            "algorithm": "random_forest",
            "version": "incumbent",
            "model": models[INCUMBENT_KEY],
            "sha256": None,
        },
        FINALIST_KEYS["logistic_regression"]: {
            "key": FINALIST_KEYS["logistic_regression"],
            "role": "finalist",
            "algorithm": "logistic_regression",
            "version": campaign["finalists"]["finalists"]["logistic_regression"]["feature_variant"],
            "model": finalists["logistic_regression"],
            "sha256": campaign["finalists"]["finalists"]["logistic_regression"]["sha256"],
        },
        FINALIST_KEYS["random_forest"]: {
            "key": FINALIST_KEYS["random_forest"],
            "role": "finalist",
            "algorithm": "random_forest",
            "version": campaign["finalists"]["finalists"]["random_forest"]["feature_variant"],
            "model": finalists["random_forest"],
            "sha256": campaign["finalists"]["finalists"]["random_forest"]["sha256"],
        },
    }

    probabilities: dict[str, np.ndarray] = {}
    for key, entry in participants.items():
        probabilities[key] = entry["model"].predict_proba(x_val)[:, 1]
        validation[key] = evaluate(entry["model"], x_val, y_val)

    cv_evidence: dict[str, dict[str, Any]] = {}
    for algorithm, key in FINALIST_KEYS.items():
        record = campaign["finalists"]["finalists"][algorithm]
        cv_evidence[key] = {
            "cv_mean_roc_auc": record["cv_mean_roc_auc"],
            "control_mean_roc_auc": record["control_mean_roc_auc"],
            "cv_gain_over_control": record["cv_gain_over_control"],
            "cv_trial_id": record["cv_trial_id"],
            "integrity": _campaign_integrity(campaign, algorithm, train_sha256),
        }

    models_payload = {
        key: {field: value for field, value in entry.items() if field != "model"}
        for key, entry in participants.items()
    }
    comparison = run_final_comparison(
        config,
        optimization,
        target=y_val,
        probabilities=probabilities,
        models=models_payload,
        incumbent_key=INCUMBENT_KEY,
        cv_evidence=cv_evidence,
        stability=campaign["stability"],
        validation_sha256=validation_sha256,
    )
    decision = comparison["decision"]
    selected_key = decision["selected"]
    best_name = participants[selected_key]["algorithm"]
    best_model = participants[selected_key]["model"]
    selected_version = {
        "kind": "optimized_finalist" if decision["action"] == "promote" else "incumbent",
        "candidate_id": selected_key,
        "algorithm": best_name,
        "experiment_id": experiment_id,
        "decision": decision["action"],
        "sha256": participants[selected_key]["sha256"],
    }

    # The validation probabilities of the round are stored so the dashboard can draw
    # the ROC and PR curves of exactly these models. The file stays outside the Git:
    # it holds one row per client.
    selection_dir = models_dir / "optimization" / experiment_id / SELECTION_DIR_NAME
    selection_dir.mkdir(parents=True, exist_ok=True)
    predictions = pd.DataFrame(
        {
            "ID": ids,
            "target": np.asarray(y_val),
        }
    )
    for key, probability in probabilities.items():
        predictions[key] = probability
    predictions.to_csv(selection_dir / PREDICTIONS_FILE, index=False)

    write_comparison(
        comparison,
        reports_dir / "optimization" / experiment_id / SELECTION_DIR_NAME / COMPARISON_FILE,
    )

    # The incumbent is archived before the published outputs are overwritten.
    incumbent_dir = models_dir / "optimization" / experiment_id / INCUMBENT_DIR_NAME
    incumbent_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(models[INCUMBENT_KEY], incumbent_dir / "random_forest_current.joblib")
    (incumbent_dir / "random_forest_current.json").write_text(
        json.dumps(
            {
                "algorithm": "random_forest",
                "version": "incumbent",
                "params": config["modeling"]["random_forest"],
                "sha256": file_sha256(incumbent_dir / "random_forest_current.joblib"),
                "train_sha256": train_sha256,
                "note": (
                    "Copia rastreada do RF vigente, preservada antes de sobrescrever "
                    "os artefatos publicados."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return comparison, best_name, best_model, selected_version


def validation_frame_ids(ids: np.ndarray) -> np.ndarray:
    """Client identifiers of the validation split, kept to align the probabilities."""
    return np.asarray(ids)


def run_training(
    config: dict[str, Any],
    *,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    models_dir: str | Path = MODELS_DIR,
    reports_dir: str | Path = REPORTS_DIR,
    figures_dir: str | Path = DEFAULT_FIGURES_DIR,
    optimization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fit both candidates, compare them on validation and freeze the selected model.

    With ``optimization`` the stage additionally runs the campaign's validation round
    and freezes its decision, as described in plan 1.6.
    """
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
    train_sha256 = file_sha256(processed_dir / "train.csv")
    validation_sha256 = file_sha256(processed_dir / "validation.csv")

    models = build_models(config)
    validation: dict[str, dict[str, Any]] = {}
    fit_info: dict[str, dict[str, Any]] = {}
    resources: dict[str, dict[str, Any]] = {}
    for name, model in models.items():
        (fitted, convergence), cost = measure_resources(
            lambda model=model: fit_with_convergence(model, x_train, y_train)
        )
        models[name] = fitted
        fit_info[name] = convergence
        resources[name] = cost

    for name, model in models.items():
        validation[name] = evaluate(model, x_val, y_val)

    metric = config["modeling"]["primary_metric"]
    baseline = config["modeling"].get("baseline", "logistic_regression")
    priority = tuple(config["modeling"]["candidates"])

    campaign: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    selected_version: dict[str, Any] | None = None
    best_model = None
    best_name = ""

    if optimization is None:
        best_name = select_best(validation, metric, baseline=baseline, priority=priority)
        best_model = models[best_name]
    else:
        campaign = _load_campaign(optimization, reports_dir, models_dir)
        comparison, best_name, best_model, selected_version = _run_campaign_round(
            config,
            optimization,
            campaign,
            models,
            x_val,
            y_val,
            validation_frame[config["dataset"]["id_column"]].to_numpy(),
            validation,
            models_dir=models_dir,
            reports_dir=reports_dir,
            train_sha256=train_sha256,
            validation_sha256=validation_sha256,
        )

    if best_model is None:
        raise RuntimeError("No model was selected")

    plotted = dict(models)
    if campaign is not None:
        for algorithm, key in FINALIST_KEYS.items():
            record = campaign["finalists"]["finalists"][algorithm]
            plotted[key] = joblib.load(
                campaign["paths"]["finalists"] / Path(record["artifact"]).name
            )
    _plot_roc(plotted, x_val, y_val, figures_dir)
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
            "version": "control",
            "role": "control",
            "hyperparameters": config["modeling"][name],
            "converged": fit_info[name]["converged"],
        }
    if campaign is not None:
        for algorithm, key in FINALIST_KEYS.items():
            record = campaign["finalists"]["finalists"][algorithm]
            candidates[key] = {
                "path": f"optimization/{optimization['experiment_id']}/{record['artifact']}",
                "sha256": record["sha256"],
                "selected": False,
                "version": record["feature_variant"],
                "role": "finalist",
                "hyperparameters": record["params"],
                "converged": record["converged"],
            }
        # The published artifact is the incumbent when the campaign keeps the current
        # model: the indicator must not point to a rejected finalist.
        promoted = selected_version["kind"] == "optimized_finalist"
        candidates[selected_version["candidate_id"]]["selected"] = promoted
        candidates[INCUMBENT_KEY]["selected"] = not promoted
        candidates[CONTROL_KEY]["selected"] = False

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
            "rule": (
                "highest_validation_metric_with_baseline_tie_break"
                if optimization is None
                else "optimization_campaign_predeclared_criteria"
            ),
            "metric": metric,
            "baseline": baseline if optimization is None else INCUMBENT_KEY,
            "tie_break": config["modeling"].get("tie_break", "baseline"),
            "rounded_metrics_used_for_decision": False,
            "scores": {name: values[metric] for name, values in validation.items()},
        },
        "fit": fit_info,
        "reload_check": reload_check,
    }
    if comparison is not None and selected_version is not None:
        metrics["selected_version"] = selected_version
        metrics["optimization"] = {
            "experiment_id": optimization["experiment_id"],
            "protocol_version": optimization["protocol_version"],
            "decision": comparison["decision"],
            "comparison_report": (
                f"reports/optimization/{optimization['experiment_id']}/"
                f"{SELECTION_DIR_NAME}/{COMPARISON_FILE}"
            ),
            "comparison_sha256": file_sha256(
                reports_dir
                / "optimization"
                / optimization["experiment_id"]
                / SELECTION_DIR_NAME
                / COMPARISON_FILE
            ),
            "candidates": {
                key: {
                    "algorithm": entry["algorithm"],
                    "version": entry["version"],
                    "sha256": entry["sha256"],
                    "cv_mean_roc_auc": campaign["finalists"]["finalists"][entry["algorithm"]][
                        "cv_mean_roc_auc"
                    ],
                    "control_mean_roc_auc": campaign["finalists"]["finalists"][entry["algorithm"]][
                        "control_mean_roc_auc"
                    ],
                    "validation_roc_auc": validation[key][metric],
                }
                for key, entry in comparison["models"].items()
                if entry["role"] == "finalist"
            },
            "ablation": campaign["ablation"],
            "stability": campaign["stability"],
            "fold_fingerprint": campaign["finalists"]["fold_fingerprint"],
            "train_sha256": train_sha256,
            "validation_sha256": validation_sha256,
            "note": (
                "A rodada de validacao da campanha e a do fluxo publicado sao a mesma "
                "rodada: incumbent, controle e finalistas foram pontuados juntos."
            ),
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
        "train_sha256": train_sha256,
        "validation_sha256": validation_sha256,
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
    if comparison is not None and selected_version is not None:
        uses_ratios = (
            selected_version["kind"] == "optimized_finalist"
            and campaign["finalists"]["finalists"][best_name]["feature_variant"] == "base+ratios"
        )
        metadata["selection_rationale"] = (
            f"Campanha {optimization['experiment_id']}: decisao "
            f"{comparison['decision']['action']}. "
            f"{comparison['decision']['reason']} "
            "O conjunto de teste nao participa da selecao."
        )
        metadata["selected_version"] = selected_version
        if selected_version["kind"] == "optimized_finalist":
            record = campaign["finalists"]["finalists"][best_name]
            metadata["selected_version"]["published_from"] = {
                "candidate_id": selected_version["candidate_id"],
                "artifact": (
                    f"models/optimization/{optimization['experiment_id']}/{record['artifact']}"
                ),
                "artifact_sha256": record["sha256"],
                "max_abs_probability_difference": reload_check["max_abs_probability_difference"],
                "tolerance": RELOAD_TOLERANCE,
                "note": (
                    "O artefato publicado e uma reserializacao do finalista: as "
                    "probabilidades sao equivalentes dentro da tolerancia, mas o hash "
                    "do arquivo pode diferir do finalista original."
                ),
            }
        metadata["hyperparameters"] = (
            campaign["finalists"]["finalists"][best_name]["params"]
            if selected_version["kind"] == "optimized_finalist"
            else config["modeling"][best_name]
        )
        metadata["external_features"] = features
        metadata["internal_features"] = features + (
            list(RATIO_FEATURE_NAMES) if uses_ratios else []
        )
        metadata["optimization"] = metrics["optimization"]
        metadata["previous_model"] = {
            "algorithm": "random_forest",
            "sha256": file_sha256(
                models_dir
                / "optimization"
                / optimization["experiment_id"]
                / INCUMBENT_DIR_NAME
                / "random_forest_current.joblib"
            ),
            "archive": (
                f"models/optimization/{optimization['experiment_id']}/"
                f"{INCUMBENT_DIR_NAME}/random_forest_current.joblib"
            ),
            "note": "Copia rastreada do modelo vigente antes da promocao.",
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
    parser.add_argument("--optimization-config", default=None)
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--figures-dir", default=str(DEFAULT_FIGURES_DIR))
    args = parser.parse_args(argv)

    optimization = None
    if args.optimization_config:
        from credit_monitoring.models.tune import load_optimization_config

        optimization = load_optimization_config(args.optimization_config)

    metrics = run_training(
        load_config(args.config),
        processed_dir=args.processed_dir,
        models_dir=args.models_dir,
        reports_dir=args.reports_dir,
        figures_dir=args.figures_dir,
        optimization=optimization,
    )
    print(
        f"Modelo selecionado: {metrics['selected_model']} "
        f"(validacao {metrics['primary_metric']}="
        f"{metrics['validation'][metrics['selected_model']][metrics['primary_metric']]:.4f})"
    )
    if "optimization" in metrics:
        print(
            f"Decisao da campanha {metrics['optimization']['experiment_id']}: "
            f"{metrics['optimization']['decision']['action']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
