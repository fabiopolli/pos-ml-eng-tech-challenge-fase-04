"""Limited optimization campaign for the credit scoring models (plan 1.6).

This module implements the executable packages **1.6-O1** (protocol and baseline
preservation), **1.6-O2** (search on the training split) and **1.6-O3** (single
financial ablation and finalist freezing).

Hard boundaries enforced by the code, not only by the plan:

- the campaign reads **only** ``data/processed/train.csv``; there is no code path
  that opens ``validation.csv`` or ``test.csv``;
- every transformation lives inside the ``Pipeline``, so the scaler and the ratio
  features are fitted inside each fold, never on the 21,000 rows before the
  cross-validation;
- the folds are the same for every candidate and control
  (``StratifiedKFold(n_splits=5, shuffle=True, random_state=42)``);
- the number of estimator fits is bounded by the budget declared in
  ``configs/optimization.yaml``;
- failures are recorded, never converted into a zero score and never removed from
  the attempt count;
- wall-clock and memory measurements are written to a **local** file that is not
  tracked by DVC, so a re-run keeps the same artifact hashes.

The final validation round and the promotion decision live in
:mod:`credit_monitoring.models.promotion`.
"""

import argparse
import hashlib
import json
import platform
import resource
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import ParameterSampler, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from credit_monitoring.config import feature_columns, load_config
from credit_monitoring.contracts import validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.models.features import FinancialRatioTransformer
from credit_monitoring.models.metrics import fit_with_convergence
from credit_monitoring.paths import MODELS_DIR, PROCESSED_DATA_DIR, REPORTS_DIR

TUNING_DIR_NAME = "tuning"
FINALISTS_DIR_NAME = "finalists"
MANIFEST_FILE = "manifest.json"
TRIALS_FILE = "trials.json"
CONTROLS_FILE = "controls.json"
ABLATION_FILE = "ablation.json"
STABILITY_FILE = "stability.json"
FINALISTS_FILE = "finalists.json"
RESOURCES_FILE = "resources.json"

FEATURE_VARIANTS = ("base", "base+ratios")
ALGORITHMS = ("logistic_regression", "random_forest")


class BudgetExceeded(RuntimeError):
    """Raised when the campaign would exceed the declared fit budget."""


@dataclass
class FitBudget:
    """Counts estimator fits and refuses to exceed the declared ceiling."""

    max_fits: int
    used: int = 0
    per_stage: dict[str, int] = field(default_factory=dict)

    def spend(self, stage: str, amount: int = 1) -> None:
        if self.used + amount > self.max_fits:
            raise BudgetExceeded(
                f"Fit budget of {self.max_fits} exhausted before '{stage}' "
                f"({self.used} used). The campaign stops instead of running partially."
            )
        self.used += amount
        self.per_stage[stage] = self.per_stage.get(stage, 0) + amount


def load_optimization_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read the frozen campaign protocol."""
    import yaml

    from credit_monitoring.paths import CONFIG_DIR

    config_path = Path(path) if path is not None else CONFIG_DIR / "optimization.yaml"
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict) or "optimization" not in loaded:
        raise ValueError(f"Invalid optimization configuration: {config_path}")
    return loaded["optimization"]


def campaign_paths(
    reports_root: str | Path, models_root: str | Path, experiment_id: str
) -> dict[str, Path]:
    """Directories owned by the campaign.

    ``reports/<root>/optimization/<experiment_id>/tuning`` and
    ``models/<root>/optimization/<experiment_id>/finalists`` belong to this
    stage; the ``selection`` directories belong to the promotion stage and never
    overlap.
    """
    reports_root = Path(reports_root)
    models_root = Path(models_root)
    return {
        "reports": reports_root / "optimization" / experiment_id / TUNING_DIR_NAME,
        "resources": reports_root / "optimization" / experiment_id / RESOURCES_FILE,
        "finalists": models_root / "optimization" / experiment_id / FINALISTS_DIR_NAME,
    }


def build_trial_list(optimization: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Effective and ordered trial list of the search, persisted before any fit.

    The Random Forest space is sampled with ``ParameterSampler``; the Logistic
    Regression space is the full 12-configuration grid. Configurations are
    distinct: a duplicated draw is discarded and the next distinct one takes its
    place.
    """
    search = optimization["search"]
    forest: list[dict[str, Any]] = []
    grid = {key: list(values) for key, values in search["random_forest"]["grid"].items()}
    wanted = int(search["random_forest"]["n_draws"])
    seen: set[str] = set()
    for n_iter in (wanted, wanted * 2, wanted * 4, wanted * 8, wanted * 16):
        sampler = ParameterSampler(
            grid, n_iter=n_iter, random_state=int(search["random_forest"]["sampler_seed"])
        )
        for params in sampler:
            signature = json.dumps(params, sort_keys=True, default=str)
            if signature in seen:
                continue
            seen.add(signature)
            forest.append(dict(params))
            if len(forest) == wanted:
                break
        if len(forest) == wanted:
            break
    if len(forest) != wanted:
        raise ValueError(
            f"Could not draw {wanted} distinct Random Forest configurations "
            f"from the declared space (got {len(forest)})"
        )

    logistic: list[dict[str, Any]] = []
    for penalty_value in search["logistic_regression"]["C"]:
        for weight in search["logistic_regression"]["class_weight"]:
            logistic.append(
                {
                    "C": penalty_value,
                    "class_weight": weight,
                    "max_iter": int(search["logistic_regression"]["max_iter"]),
                }
            )
    return {"random_forest": forest, "logistic_regression": logistic}


def build_folds(
    target: pd.Series, folds_config: dict[str, Any]
) -> list[tuple[np.ndarray, np.ndarray]]:
    """The five stratified folds shared by every candidate and control."""
    splitter = StratifiedKFold(
        n_splits=int(folds_config["n_splits"]),
        shuffle=bool(folds_config["shuffle"]),
        random_state=int(folds_config["random_state"]),
    )
    return list(splitter.split(np.zeros(len(target)), target))


def fold_fingerprint(folds: list[tuple[np.ndarray, np.ndarray]]) -> str:
    """Stable identifier of the fold partition, recorded with the results."""
    payload = json.dumps(
        [[train.tolist(), valid.tolist()] for train, valid in folds], sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_pipeline(
    algorithm: str,
    params: dict[str, Any],
    *,
    seed: int,
    feature_variant: str = "base",
    min_denominator: float = 1.0,
    n_jobs: int = 1,
) -> Pipeline:
    """Build the pipeline of a candidate.

    The scaler and the ratio transformer are steps of the pipeline, so they are
    fitted inside each fold. The Random Forest uses ``criterion=gini`` and
    ``bootstrap=True`` with the estimator seed fixed by the protocol.
    """
    steps: list[tuple[str, Any]] = []
    if feature_variant == "base+ratios":
        steps.append(("ratios", FinancialRatioTransformer(min_denominator=min_denominator)))
    if algorithm == "logistic_regression":
        estimator = LogisticRegression(
            random_state=seed,
            solver="lbfgs",
            penalty="l2",
            **params,
        )
        steps.append(("scaler", StandardScaler()))
        steps.append(("classifier", estimator))
    elif algorithm == "random_forest":
        estimator = RandomForestClassifier(
            random_state=seed,
            criterion="gini",
            bootstrap=True,
            n_jobs=n_jobs,
            **params,
        )
        steps.append(("classifier", estimator))
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    return Pipeline(steps)


def pipeline_steps(algorithm: str, feature_variant: str) -> list[str]:
    """Names of the pipeline steps, recorded with the finalist."""
    steps: list[str] = []
    if feature_variant == "base+ratios":
        steps.append("ratios")
    if algorithm == "logistic_regression":
        steps.append("scaler")
    steps.append("classifier")
    return steps


def _rss_mib() -> float | None:
    try:
        with open("/proc/self/statm", encoding="utf-8") as handle:
            pages = int(handle.read().split()[1])
    except (OSError, IndexError, ValueError):
        return None
    return round(pages * resource.getpagesize() / (1024 * 1024), 3)


def run_trial(
    trial: dict[str, Any],
    x: pd.DataFrame,
    y: pd.Series,
    folds: list[tuple[np.ndarray, np.ndarray]],
    *,
    budget: FitBudget,
    n_jobs: int,
    min_denominator: float,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Fit and score one configuration on the five folds.

    Returns the trial record. A non-converged Logistic Regression is a **failed**
    trial: it keeps its place in the attempt count and never becomes a score.
    """
    algorithm = trial["algorithm"]
    params = dict(trial["params"])
    seed = int(trial["seed"])
    feature_variant = trial["feature_variant"]

    fold_records: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    status = "ok"
    failure: str | None = None

    for index, (train_index, valid_index) in enumerate(folds, start=1):
        # One estimator fit per fold: the budget counts adjustments, not trials.
        budget.spend("fold_fit")
        pipeline = build_pipeline(
            algorithm,
            params,
            seed=seed,
            feature_variant=feature_variant,
            min_denominator=min_denominator,
            n_jobs=n_jobs,
        )
        x_train = x.iloc[train_index]
        y_train = y.iloc[train_index]
        x_valid = x.iloc[valid_index]
        y_valid = y.iloc[valid_index]
        try:
            fitted, convergence = fit_with_convergence(pipeline, x_train, y_train)
        except Exception as error:  # noqa: BLE001 - the failure must be recorded
            status = "failed"
            failure = f"{type(error).__name__}: {error}"
            break
        if not convergence["converged"]:
            status = "failed"
            failure = "Logistic Regression did not converge: " + "; ".join(
                convergence["convergence_warnings"]
            )
            break
        probability = fitted.predict_proba(x_valid)[:, 1]
        fitted_probability = fitted.predict_proba(x_train)[:, 1]
        fold_records.append(
            {
                "fold": index,
                "roc_auc": float(roc_auc_score(y_valid, probability)),
                "fit_roc_auc": float(roc_auc_score(y_train, fitted_probability)),
                "train_rows": int(len(train_index)),
                "valid_rows": int(len(valid_index)),
            }
        )

    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    resources.setdefault("trials", {})[trial["trial_id"]] = {
        "wall_time_s": round(wall, 3),
        "cpu_time_s": round(cpu, 3),
        "folds_completed": len(fold_records),
        "fits": len(fold_records),
        "status": status,
    }

    record = dict(trial)
    record["status"] = status
    record["failure"] = failure
    record["folds"] = fold_records
    if status == "ok" and fold_records:
        scores = [fold["roc_auc"] for fold in fold_records]
        record["mean_roc_auc"] = float(np.mean(scores))
        record["std_roc_auc"] = float(np.std(scores, ddof=0))
        record["fit_scores"] = [fold["fit_roc_auc"] for fold in fold_records]
    else:
        record["mean_roc_auc"] = None
        record["std_roc_auc"] = None
        record["fit_scores"] = []
    return record


def rank_trials(trials: list[dict[str, Any]], control_trial_id: str) -> str:
    """Highest mean fold ROC-AUC wins.

    An exact tie favours the control; between tied new configurations the first
    one in the persisted list wins. The comparison uses the unrounded values.
    """
    eligible = [trial for trial in trials if trial["status"] == "ok"]
    if not eligible:
        raise ValueError("No successful trial to rank")
    best = max(trial["mean_roc_auc"] for trial in eligible)
    tied = [trial for trial in eligible if trial["mean_roc_auc"] == best]
    for trial in tied:
        if trial["trial_id"] == control_trial_id:
            return control_trial_id
    return tied[0]["trial_id"]


def _trial_id(algorithm: str, source: str, index: int) -> str:
    return f"{algorithm}:{source}:{index:02d}"


def _control_params(config: dict[str, Any], algorithm: str) -> dict[str, Any]:
    """Pipeline parameters of the current control.

    The control of the Logistic Regression keeps the ``max_iter`` declared in the
    project configuration (1000); the search grid uses 5000, as the plan states.
    """
    declared = dict(config["modeling"][algorithm])
    if algorithm == "logistic_regression":
        return {
            "C": declared["C"],
            "class_weight": declared["class_weight"],
            "max_iter": declared.get("max_iter", 5000),
        }
    return {
        "n_estimators": declared["n_estimators"],
        "max_depth": declared["max_depth"],
        "min_samples_leaf": declared["min_samples_leaf"],
        "class_weight": declared["class_weight"],
    }


def _source_files() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here,
        here.parent / "features.py",
        here.parent / "metrics.py",
        here.parent.parent / "config.py",
        here.parent.parent / "paths.py",
    ]


def _source_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    hashes: dict[str, str] = {}
    for path in _source_files():
        if path.is_file():
            hashes[str(path.relative_to(root))] = file_sha256(path)
    return hashes


def _versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
    }


def _config_fingerprint(config: dict[str, Any], optimization: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "project": config["project"],
            "dataset": {
                "financial_features": config["dataset"]["financial_features"],
                "canonical_target": config["dataset"]["canonical_target"],
                "id_column": config["dataset"]["id_column"],
            },
            "contract": config["contract"],
            "modeling": config["modeling"],
            "optimization": optimization,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_training_split(
    processed_dir: str | Path, config: dict[str, Any], split: str = "train"
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Read and validate **only** the training split.

    The function refuses any split other than ``train``: the campaign has no code
    path that opens the validation or the test split.
    """
    if split != "train":
        raise ValueError(f"The campaign may only read the train split, got '{split}'")
    processed_dir = Path(processed_dir)
    path = processed_dir / "train.csv"
    frame = validate_batch(pd.read_csv(path), config, labeled=True)
    features = feature_columns(config)
    target = config["dataset"]["canonical_target"]
    return frame[features], frame[target], frame


def run_campaign(
    config: dict[str, Any],
    optimization: dict[str, Any],
    *,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    reports_root: str | Path = REPORTS_DIR,
    models_root: str | Path = MODELS_DIR,
) -> dict[str, Any]:
    """Execute the whole campaign on the training split and freeze the finalists."""
    processed_dir = Path(processed_dir)
    reports_root = Path(reports_root)
    models_root = Path(models_root)
    experiment_id = optimization["experiment_id"]
    paths = campaign_paths(reports_root, models_root, experiment_id)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    paths["finalists"].mkdir(parents=True, exist_ok=True)

    resources: dict[str, Any] = {
        "note": (
            "Medicoes locais de execucao (tempo, CPU, pico de RSS). Fica fora do DVC: "
            "variam a cada execucao e nao podem mudar o hash dos artefatos versionados."
        ),
        "platform": platform.platform(),
    }

    x, y, frame = load_training_split(processed_dir, config)
    folds = build_folds(y, optimization["folds"])
    seed = int(optimization["seeds"]["primary"])
    n_jobs = int(optimization.get("n_jobs", 1))
    min_denominator = float(optimization["ratio_features"]["min_denominator"])
    budget = FitBudget(max_fits=int(optimization["budget"]["max_fits"]))

    trial_list = build_trial_list(optimization)

    # --- O1: the protocol is frozen before any fit happens -------------------
    manifest = {
        "protocol_version": optimization["protocol_version"],
        "experiment_id": experiment_id,
        "state": "protocol_frozen_before_results",
        "primary_metric": optimization["primary_metric"],
        "threshold": optimization["threshold"],
        "folds": {
            **optimization["folds"],
            "fingerprint": fold_fingerprint(folds),
            "train_rows": int(len(frame)),
            "target_positives": int(y.sum()),
            "target_prevalence": float(y.mean()),
        },
        "seeds": optimization["seeds"],
        "budget": optimization["budget"],
        "criteria": optimization["criteria"],
        "ratio_features": optimization["ratio_features"],
        "search": optimization["search"],
        "trial_lists": trial_list,
        "controls": {algorithm: _control_params(config, algorithm) for algorithm in ALGORITHMS},
        "inputs": {
            "train_sha256": file_sha256(processed_dir / "train.csv"),
            "train_rows": int(len(frame)),
            "id_column": config["dataset"]["id_column"],
            "unique_ids": int(frame[config["dataset"]["id_column"]].nunique()),
        },
        "sources": _source_hashes(),
        "versions": _versions(),
        "config_fingerprint": _config_fingerprint(config, optimization),
        "isolation": {
            "reads": ["data/processed/train.csv"],
            "never_reads": ["data/processed/validation.csv", "data/processed/test.csv"],
            "statement": (
                "A busca, a ablacao e a checagem de estabilidade usam apenas o treino. "
                "A validacao e consultada uma unica vez, na rodada comparativa do "
                "estagio de selecao; o teste nao participa da campanha."
            ),
        },
    }
    (paths["reports"] / MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # --- O2: controls and search on the training split -----------------------
    trials: list[dict[str, Any]] = []
    control_records: dict[str, dict[str, Any]] = {}
    for algorithm in ALGORITHMS:
        trial = {
            "trial_id": _trial_id(algorithm, "control", 0),
            "algorithm": algorithm,
            "source": "control",
            "params": _control_params(config, algorithm),
            "feature_variant": "base",
            "seed": seed,
            "order": 0,
        }
        record = run_trial(
            trial,
            x,
            y,
            folds,
            budget=budget,
            n_jobs=n_jobs,
            min_denominator=min_denominator,
            resources=resources,
        )
        trials.append(record)
        control_records[algorithm] = record

    for algorithm in ALGORITHMS:
        for index, params in enumerate(trial_list[algorithm], start=1):
            trial = {
                "trial_id": _trial_id(algorithm, "search", index),
                "algorithm": algorithm,
                "source": "search",
                "params": params,
                "feature_variant": "base",
                "seed": seed,
                "order": index,
            }
            trials.append(
                run_trial(
                    trial,
                    x,
                    y,
                    folds,
                    budget=budget,
                    n_jobs=n_jobs,
                    min_denominator=min_denominator,
                    resources=resources,
                )
            )

    family_best: dict[str, str] = {}
    for algorithm in ALGORITHMS:
        family_trials = [trial for trial in trials if trial["algorithm"] == algorithm]
        control_id = _trial_id(algorithm, "control", 0)
        family_best[algorithm] = rank_trials(family_trials, control_id)

    (paths["reports"] / TRIALS_FILE).write_text(
        json.dumps({"trials": trials}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (paths["reports"] / CONTROLS_FILE).write_text(
        json.dumps(
            {
                algorithm: {
                    "trial_id": control_records[algorithm]["trial_id"],
                    "params": control_records[algorithm]["params"],
                    "status": control_records[algorithm]["status"],
                    "mean_roc_auc": control_records[algorithm]["mean_roc_auc"],
                    "std_roc_auc": control_records[algorithm]["std_roc_auc"],
                    "fold_scores": [
                        fold["roc_auc"] for fold in control_records[algorithm]["folds"]
                    ],
                    "fit_scores": control_records[algorithm]["fit_scores"],
                    "note": (
                        "Media de CV nao e compativel com o ROC-AUC de validacao: sao "
                        "particoes e estimadores diferentes."
                    ),
                }
                for algorithm in ALGORITHMS
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # --- O3: one pre-defined financial ablation per family -------------------
    ablation: dict[str, Any] = {}
    best_params: dict[str, dict[str, Any]] = {}
    for algorithm in ALGORITHMS:
        best = next(trial for trial in trials if trial["trial_id"] == family_best[algorithm])
        best_params[algorithm] = best["params"]
        ratio_trial = {
            "trial_id": _trial_id(algorithm, "ablation", 0),
            "algorithm": algorithm,
            "source": "ablation",
            "params": best["params"],
            "feature_variant": "base+ratios",
            "seed": seed,
            "order": 0,
        }
        ratio_record = run_trial(
            ratio_trial,
            x,
            y,
            folds,
            budget=budget,
            n_jobs=n_jobs,
            min_denominator=min_denominator,
            resources=resources,
        )
        base_mean = best["mean_roc_auc"]
        ratio_mean = ratio_record["mean_roc_auc"]
        gain = None
        if base_mean is not None and ratio_mean is not None:
            gain = ratio_mean - base_mean
        adopt = bool(
            gain is not None and gain >= float(optimization["criteria"]["min_ablation_gain"])
        )
        ablation[algorithm] = {
            "base_trial_id": best["trial_id"],
            "base_mean_roc_auc": base_mean,
            "base_reused_from_search": True,
            "ratio_trial_id": ratio_record["trial_id"],
            "ratio_status": ratio_record["status"],
            "ratio_mean_roc_auc": ratio_mean,
            "ratio_fold_scores": [fold["roc_auc"] for fold in ratio_record["folds"]],
            "gain": gain,
            "min_gain_required": float(optimization["criteria"]["min_ablation_gain"]),
            "adopted": adopt,
            "decision": (
                "ratio features adopted"
                if adopt
                else "original features kept: the ablation gain did not reach the threshold"
            ),
            "formulas": {
                "bill_amt1_over_limit_bal": "BILL_AMT1 / LIMIT_BAL",
                "pay_amt1_over_limit_bal": "PAY_AMT1 / LIMIT_BAL",
                "pay_amt1_over_abs_bill_amt1": "PAY_AMT1 / max(abs(BILL_AMT1), 1.0)",
            },
        }
    (paths["reports"] / ABLATION_FILE).write_text(
        json.dumps(ablation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    finalist_variants = {
        algorithm: ("base+ratios" if ablation[algorithm]["adopted"] else "base")
        for algorithm in ALGORITHMS
    }

    # --- O3: stability of the Random Forest finalist ------------------------
    stability: dict[str, Any] = {"algorithm": "random_forest", "seeds": {}}
    control_mean = control_records["random_forest"]["mean_roc_auc"]
    forest_best = next(
        trial for trial in trials if trial["trial_id"] == family_best["random_forest"]
    )
    finalist_mean = forest_best["mean_roc_auc"]
    if finalist_variants["random_forest"] == "base+ratios":
        finalist_mean = ablation["random_forest"]["ratio_mean_roc_auc"]
    for stability_seed in optimization["seeds"]["stability"]:
        trial = {
            "trial_id": _trial_id("random_forest", "stability", stability_seed),
            "algorithm": "random_forest",
            "source": "stability",
            "params": best_params["random_forest"],
            "feature_variant": finalist_variants["random_forest"],
            "seed": int(stability_seed),
            "order": 0,
        }
        record = run_trial(
            trial,
            x,
            y,
            folds,
            budget=budget,
            n_jobs=n_jobs,
            min_denominator=min_denominator,
            resources=resources,
        )
        stability["seeds"][str(stability_seed)] = {
            "mean_roc_auc": record["mean_roc_auc"],
            "fold_scores": [fold["roc_auc"] for fold in record["folds"]],
            "status": record["status"],
        }
    repetition_means = [
        value["mean_roc_auc"]
        for value in stability["seeds"].values()
        if value["mean_roc_auc"] is not None
    ]
    stability["primary_seed"] = int(optimization["seeds"]["primary"])
    stability["primary_mean_roc_auc"] = finalist_mean
    stability["control_mean_roc_auc"] = control_mean
    stability["repetition_mean_roc_auc"] = (
        float(np.mean(repetition_means)) if repetition_means else None
    )
    stability["repetitions_beat_control"] = bool(
        stability["repetition_mean_roc_auc"] is not None
        and control_mean is not None
        and stability["repetition_mean_roc_auc"] > control_mean
    )
    stability["note"] = (
        "As repeticoes 17 e 73 sao reportadas com a semente 42, sem escolher a melhor. "
        "A versao final mantem a semente 42."
    )
    (paths["reports"] / STABILITY_FILE).write_text(
        json.dumps(stability, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # --- O3: freeze one finalist per algorithm -------------------------------
    finalists: dict[str, Any] = {}
    for algorithm in ALGORITHMS:
        variant = finalist_variants[algorithm]
        budget.spend("final_fit")
        pipeline = build_pipeline(
            algorithm,
            best_params[algorithm],
            seed=seed,
            feature_variant=variant,
            min_denominator=min_denominator,
            n_jobs=n_jobs,
        )
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        fitted, convergence = fit_with_convergence(pipeline, x, y)
        target_path = paths["finalists"] / f"{algorithm}.joblib"
        joblib.dump(fitted, target_path)
        resources.setdefault("final_fits", {})[algorithm] = {
            "wall_time_s": round(time.perf_counter() - wall_start, 3),
            "cpu_time_s": round(time.process_time() - cpu_start, 3),
        }
        best = next(trial for trial in trials if trial["trial_id"] == family_best[algorithm])
        mean = best["mean_roc_auc"]
        if variant == "base+ratios":
            mean = ablation[algorithm]["ratio_mean_roc_auc"]
        finalists[algorithm] = {
            "algorithm": algorithm,
            "params": best_params[algorithm],
            "feature_variant": variant,
            "seed": seed,
            "pipeline_steps": pipeline_steps(algorithm, variant),
            "artifact": f"{FINALISTS_DIR_NAME}/{target_path.name}",
            "sha256": file_sha256(target_path),
            "train_sha256": manifest["inputs"]["train_sha256"],
            "converged": convergence["converged"],
            "cv_trial_id": family_best[algorithm],
            "cv_mean_roc_auc": mean,
            "control_mean_roc_auc": control_records[algorithm]["mean_roc_auc"],
            "cv_gain_over_control": (
                None
                if mean is None or control_records[algorithm]["mean_roc_auc"] is None
                else mean - control_records[algorithm]["mean_roc_auc"]
            ),
        }

    finalists_payload = {
        "experiment_id": experiment_id,
        "protocol_version": optimization["protocol_version"],
        "fold_fingerprint": manifest["folds"]["fingerprint"],
        "train_sha256": manifest["inputs"]["train_sha256"],
        "finalists": finalists,
        "stability": stability,
        "budget": {
            "max_fits": budget.max_fits,
            "used_fits": budget.used,
            "per_stage": budget.per_stage,
            "counting": (
                "Um ajuste equivale a um ajuste do estimador: um fit por fold. "
                "Controles 10, busca RF 120, busca LR 60, ablacao 10, estabilidade 10 "
                "e ajustes finais 2 (212 planejados, margem de 8)."
            ),
        },
        "note": (
            "Finalistas ajustados nas 21.000 linhas do treino. Nenhum finalista foi "
            "consultado na validacao nem no teste."
        ),
    }
    (paths["reports"] / FINALISTS_FILE).write_text(
        json.dumps(finalists_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    resources["budget"] = finalists_payload["budget"]
    resources["peak_rss_mib"] = _rss_mib()
    paths["resources"].parent.mkdir(parents=True, exist_ok=True)
    paths["resources"].write_text(
        json.dumps(resources, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return finalists_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Campanha de otimizacao dos modelos (plano 1.6): controles, busca, "
            "ablacao e estabilidade, somente sobre o conjunto de treino."
        )
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--optimization-config", default=None)
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    args = parser.parse_args(argv)

    payload = run_campaign(
        load_config(args.config),
        load_optimization_config(args.optimization_config),
        processed_dir=args.processed_dir,
        reports_root=args.reports_dir,
        models_root=args.models_dir,
    )
    for algorithm, record in payload["finalists"].items():
        print(
            f"Finalista {algorithm}: {record['feature_variant']} "
            f"cv_mean_roc_auc={record['cv_mean_roc_auc']:.6f}"
        )
    print(f"Ajustes usados: {payload['budget']['used_fits']}/{payload['budget']['max_fits']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
