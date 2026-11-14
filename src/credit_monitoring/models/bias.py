"""Aggregate, descriptive bias analysis of the frozen model (plan 4.3).

The analysis scores the **original labeled validation split** with the frozen model and
the fixed threshold, then reports aggregated counts and rates per governance group
(``SEX``, ``EDUCATION``, ``MARRIAGE`` and banded ``AGE``). Rules fixed here, before any
result is read:

- the test split is never opened; the validation split already took part in model
  selection, so the numbers are descriptive and possibly optimistic;
- the demographic columns are not model inputs: they are used only to slice the
  predictions. Excluding them does not remove proxies nor prove absence of bias;
- original codes are kept as they are; undocumented codes are not given a meaning;
- groups below ``MIN_GROUP_SIZE`` rows report only their size, and a rate whose
  denominator is below ``MIN_CLASS_SIZE`` is left undefined (inconclusive);
- proportions carry a Wilson 95% interval. A wide interval means "inconclusive",
  never "no bias";
- the output holds no row, no ID and no customer value.

The run refuses to write a report when the model and the partition do not reproduce the
validation confusion matrix already recorded by the selection stage.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from credit_monitoring.config import feature_columns, load_config
from credit_monitoring.contracts import CONTRACT_VERSION, validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.models.metrics import THRESHOLD
from credit_monitoring.paths import MODELS_DIR, PROCESSED_DATA_DIR, REPORTS_DIR

# Same names as the selection stage; not imported from it because ``train`` needs the
# Unix-only ``resource`` module and this analysis must also run on Windows.
MODEL_FILE = "credit_model.joblib"
METADATA_FILE = "credit_model_metadata.json"
BIAS_REPORT_FILE = "validation_bias.json"
BIAS_REPORT_SCHEMA_VERSION = "1.0.0"
MIN_GROUP_SIZE = 30
MIN_CLASS_SIZE = 30
WILSON_Z = 1.959964
ROUNDING = 6
AGE_BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("<=29", None, 29),
    ("30-39", 30, 39),
    ("40-49", 40, 49),
    (">=50", 50, None),
)


def wilson_interval(successes: int, total: int) -> list[float] | None:
    """Wilson score interval (95%) for a proportion; ``None`` when undefined."""
    if total <= 0:
        return None
    p = successes / total
    z2 = WILSON_Z**2
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    half = WILSON_Z * math.sqrt(p * (1 - p) / total + z2 / (4 * total**2)) / denominator
    return [round(max(0.0, center - half), ROUNDING), round(min(1.0, center + half), ROUNDING)]


def _rate(successes: int, total: int, *, minimum: int) -> dict[str, Any]:
    if total < minimum:
        return {"value": None, "ci95": None, "denominator": int(total), "status": "inconclusive"}
    return {
        "value": round(successes / total, ROUNDING),
        "ci95": wilson_interval(successes, total),
        "denominator": int(total),
        "status": "ok",
    }


def group_metrics(target: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    """Aggregated metrics of one group, applying the predeclared suppression rules."""
    n = int(len(target))
    if n < MIN_GROUP_SIZE:
        return {"n": n, "status": "suppressed"}

    positives = int((target == 1).sum())
    negatives = n - positives
    tp = int(((target == 1) & (predicted == 1)).sum())
    fp = int(((target == 0) & (predicted == 1)).sum())
    fn = positives - tp
    tn = negatives - fp
    tpr = _rate(tp, positives, minimum=MIN_CLASS_SIZE)
    fnr = _rate(fn, positives, minimum=MIN_CLASS_SIZE)
    fpr = _rate(fp, negatives, minimum=MIN_CLASS_SIZE)
    complete = all(item["status"] == "ok" for item in (tpr, fnr, fpr))
    return {
        "n": n,
        "positives": positives,
        "negatives": negatives,
        "status": "ok" if complete else "partial",
        "prevalence": _rate(positives, n, minimum=MIN_GROUP_SIZE),
        "predicted_positive_rate": _rate(int(predicted.sum()), n, minimum=MIN_GROUP_SIZE),
        "tpr": tpr,
        "fnr": fnr,
        "fpr": fpr,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def age_band(age: pd.Series) -> pd.Series:
    """Assign the predeclared age bands; every age falls in exactly one band."""
    labels = pd.Series(index=age.index, dtype=object)
    for label, low, high in AGE_BANDS:
        mask = pd.Series(True, index=age.index)
        if low is not None:
            mask &= age >= low
        if high is not None:
            mask &= age <= high
        labels[mask] = label
    return labels


def group_labels(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, pd.Series]:
    """Group labels per governance feature; ``AGE`` is banded, other codes are kept as is."""
    labels: dict[str, pd.Series] = {}
    for column in config["dataset"]["governance_features"]:
        labels[column] = (
            age_band(frame[column]) if column == "AGE" else frame[column].astype(int).astype(str)
        )
    return labels


def _ordered(keys: list[str], column: str) -> list[str]:
    if column == "AGE":
        return [label for label, _, _ in AGE_BANDS if label in keys]
    return sorted(keys, key=int)


def _sha256_lf_normalized(path: Path) -> str:
    """SHA-256 with CRLF folded to LF, so a Windows checkout compares with the DVC object."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _reconcile(reports_dir: Path, selected_model: str, confusion: dict[str, int]) -> dict[str, Any]:
    metrics_path = reports_dir / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(
            f"{metrics_path} not found: the selection record is needed to reconcile the run."
        )
    recorded = json.loads(metrics_path.read_text(encoding="utf-8"))
    expected = recorded["validation"][selected_model]["confusion_matrix"]
    if expected != confusion:
        raise ValueError(
            "Model and validation partition do not reproduce the recorded validation "
            f"confusion matrix: {confusion} != {expected}. Recover the versioned artifacts "
            "with DVC before running the bias analysis."
        )
    return {
        "source": "reports/metrics.json",
        "validation_confusion_matrix_matches": True,
        "confusion_matrix": expected,
    }


def run_bias_analysis(
    config: dict[str, Any],
    *,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    models_dir: str | Path = MODELS_DIR,
    reports_dir: str | Path = REPORTS_DIR,
) -> dict[str, Any]:
    processed_dir = Path(processed_dir)
    models_dir = Path(models_dir)
    reports_dir = Path(reports_dir)

    model_path = models_dir / MODEL_FILE
    metadata_path = models_dir / METADATA_FILE
    if not model_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Frozen model not found. Run the selection stage first.")
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
        raise ValueError("The frozen feature list does not match the current configuration.")

    validation_path = processed_dir / "validation.csv"
    frame = validate_batch(pd.read_csv(validation_path), config, labeled=True)
    target = frame[config["dataset"]["canonical_target"]].to_numpy()
    threshold = metadata.get("threshold", THRESHOLD)
    model = joblib.load(model_path)
    probability = model.predict_proba(frame[features])[:, 1]
    predicted = (probability >= threshold).astype(int)

    overall = group_metrics(target, predicted)
    reconciliation = _reconcile(
        reports_dir, metadata["selected_model"], overall["confusion_matrix"]
    )

    groups: dict[str, dict[str, Any]] = {}
    for column, labels in group_labels(frame, config).items():
        values = labels.to_numpy()
        keys = _ordered(sorted(set(values)), column)
        groups[column] = {
            key: group_metrics(target[values == key], predicted[values == key]) for key in keys
        }

    payload = {
        "schema_version": BIAS_REPORT_SCHEMA_VERSION,
        "analysis": "aggregate_bias_validation",
        "selected_model": metadata["selected_model"],
        "contract_version": metadata.get("contract_version", CONTRACT_VERSION),
        "model_file_sha256": model_sha256,
        "validation_file_sha256": file_sha256(validation_path),
        "validation_sha256_lf_normalized": _sha256_lf_normalized(validation_path),
        "reconciliation": reconciliation,
        "protocol": {
            "partition": "validation",
            "partition_rows": int(len(frame)),
            "threshold": threshold,
            "positive_class": "1 = default next month (risk of default); not a credit approval",
            "model_inputs": features,
            "governance_features": list(config["dataset"]["governance_features"]),
            "test_split_used": False,
            "min_group_size": MIN_GROUP_SIZE,
            "min_class_size": MIN_CLASS_SIZE,
            "interval": "wilson_95",
            "age_bands": [label for label, _, _ in AGE_BANDS],
            "limitations": [
                "Descritivo: a validacao ja participou da selecao do modelo e pode ser otimista.",
                "Excluir demografia das entradas nao elimina proxies nem prova ausencia de vies.",
                "Intervalo largo ou grupo suprimido significa inconclusivo, nao ausencia de vies.",
                "Codigos fora da documentacao do dataset sao mantidos sem atribuir significado.",
                "Analise nao causal: diferencas entre grupos nao indicam a causa.",
            ],
        },
        "overall": overall,
        "groups": groups,
    }
    output_dir = reports_dir / "bias"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / BIAS_REPORT_FILE).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analise agregada de vies do modelo congelado na validacao rotulada."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    args = parser.parse_args(argv)

    payload = run_bias_analysis(
        load_config(args.config),
        processed_dir=args.processed_dir,
        models_dir=args.models_dir,
        reports_dir=args.reports_dir,
    )
    print(
        f"Analise de vies: {payload['selected_model']} em "
        f"{payload['protocol']['partition_rows']} linhas de validacao"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
