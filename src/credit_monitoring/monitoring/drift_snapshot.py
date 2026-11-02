"""Read and validate the frozen, aggregate-only Data Drift 1.0.2 snapshot."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCENARIO_ID = "phase-2-1.0.2"
PROTOCOL_VERSION = "1.0.2"
SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "1.0.0"
MODEL_SHA256 = "a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464"
THRESHOLD = 0.5
PSI_THRESHOLD = 0.2
PROPORTION_TOLERANCE = 1e-6
COMPARISON_IDS = (
    "reference_vs_original",
    "reference_vs_modified",
    "original_vs_modified",
)
COMPARISON_LABELS = {
    "reference_vs_original": "Referência × original (controle)",
    "reference_vs_modified": "Referência × modificado",
    "original_vs_modified": "Original × modificado",
}
INPUT_SHA256 = {
    "original": "d9f855a77f8fb6916fded48b880d18fa48e4c4816070167f4caf8af6ad874d65",
    "modified": "8da682f306f25003c98e851e84dda427b25daac41dfdf9474a13b6f641f71fc7",
}
FEATURES = (
    "LIMIT_BAL",
    "PAY_0",
    "PAY_2",
    "PAY_3",
    "PAY_4",
    "PAY_5",
    "PAY_6",
    "BILL_AMT1",
    "BILL_AMT2",
    "BILL_AMT3",
    "BILL_AMT4",
    "BILL_AMT5",
    "BILL_AMT6",
    "PAY_AMT1",
    "PAY_AMT2",
    "PAY_AMT3",
    "PAY_AMT4",
    "PAY_AMT5",
    "PAY_AMT6",
)


class DriftSnapshotError(ValueError):
    """A controlled, user-safe reason a snapshot cannot be displayed."""


@dataclass(frozen=True)
class FeatureSnapshot:
    feature: str
    score: float
    threshold: float
    drift: bool
    method: str
    comparison_operator: str
    reference_count: int
    current_count: int
    bin_labels: tuple[str, ...]
    bin_edges: tuple[float, ...]
    reference_proportions: tuple[float, ...]
    current_proportions: tuple[float, ...]


@dataclass(frozen=True)
class ComparisonSnapshot:
    comparison_id: str
    global_alert: bool
    drifted_feature_count: int
    drifted_features: tuple[str, ...]
    method: str
    reference_rows: int
    current_rows: int
    features: tuple[FeatureSnapshot, ...]


@dataclass(frozen=True)
class PredictionSummary:
    rows: int
    predicted_positives: int
    mean: float
    median: float
    p05: float
    p25: float
    p75: float
    p95: float
    std_population: float


@dataclass(frozen=True)
class DriftSnapshot:
    scenario_id: str
    protocol_version: str
    schema_version: str
    contract_version: str
    model_sha256: str
    threshold: float
    comparisons: tuple[ComparisonSnapshot, ...]
    original: PredictionSummary
    modified: PredictionSummary


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DriftSnapshotError(f"O campo {label} está ausente ou tem formato incompatível.")
    return value


def _finite(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DriftSnapshotError(f"O campo numérico {label} é incompatível.")
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise DriftSnapshotError(f"O campo numérico {label} está fora do domínio suportado.")
    return number


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DriftSnapshotError(f"A contagem {label} é incompatível.")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise DriftSnapshotError(f"O hash {label} está ausente ou é incompatível.")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DriftSnapshotError(f"Artefato ausente: {path.name}.")
    try:
        with path.open(encoding="utf-8") as stream:
            return _object(json.load(stream), path.name)
    except DriftSnapshotError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise DriftSnapshotError(f"Artefato ilegível ou JSON inválido: {path.name}.") from None


def _require_versions(results: dict[str, Any], predictions: dict[str, Any]) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "scenario_id": SCENARIO_ID,
        "contract_version": CONTRACT_VERSION,
    }
    for field, value in expected.items():
        if results.get(field) != value:
            raise DriftSnapshotError(f"Versão ou cenário não suportado em {field}.")
    for field, value in expected.items():
        if predictions.get(field) != value:
            raise DriftSnapshotError(f"Os artefatos divergem em {field}.")


def _parse_feature(
    raw: Any,
    expected_name: str,
    expected_reference_count: int,
    expected_current_count: int,
) -> FeatureSnapshot:
    item = _object(raw, f"feature {expected_name}")
    if item.get("feature") != expected_name:
        raise DriftSnapshotError("A lista de features do snapshot não corresponde ao contrato.")

    method = item.get("method")
    operator = item.get("comparison")
    if method != "custom_psi" or operator != ">":
        raise DriftSnapshotError("Método ou operador do protocolo não suportado.")

    score = _finite(item.get("score"), f"score {expected_name}", minimum=0.0)
    threshold = _finite(item.get("threshold"), f"threshold {expected_name}", minimum=0.0)
    if threshold != PSI_THRESHOLD:
        raise DriftSnapshotError("O limiar PSI não corresponde ao protocolo 1.0.2.")
    drift = item.get("drift")
    if not isinstance(drift, bool) or drift != (score > threshold):
        raise DriftSnapshotError(f"O alerta de {expected_name} diverge do score e do limiar.")

    reference_count = _count(item.get("reference_count"), f"referência {expected_name}")
    current_count = _count(item.get("current_count"), f"lote {expected_name}")
    if reference_count != expected_reference_count or current_count != expected_current_count:
        raise DriftSnapshotError(f"As contagens de {expected_name} divergem da comparação.")

    spec = _object(item.get("bin_spec"), f"bins {expected_name}")
    labels = spec.get("labels")
    edges = spec.get("edges")
    if (
        not isinstance(labels, list)
        or not labels
        or any(not isinstance(label, str) or not label for label in labels)
        or not isinstance(edges, list)
        or len(edges) != len(labels) - 2
    ):
        raise DriftSnapshotError(f"Os bins de {expected_name} têm dimensões incompatíveis.")
    numeric_edges = tuple(_finite(edge, f"borda de {expected_name}") for edge in edges)
    if any(
        numeric_edges[index] >= numeric_edges[index + 1] for index in range(len(numeric_edges) - 1)
    ):
        raise DriftSnapshotError(f"As bordas de {expected_name} não estão em ordem crescente.")
    if labels[0] != "zero" or spec.get("zero_separate") is not True:
        raise DriftSnapshotError(f"A categoria zero de {expected_name} não está identificada.")

    vectors: list[tuple[float, ...]] = []
    for name, count_key, proportions_key in (
        ("referência", "reference_bin_counts", "reference_proportions"),
        ("lote", "current_bin_counts", "current_proportions"),
    ):
        counts = item.get(count_key)
        proportions = item.get(proportions_key)
        if (
            not isinstance(counts, list)
            or len(counts) != len(labels)
            or not isinstance(proportions, list)
            or len(proportions) != len(labels)
        ):
            raise DriftSnapshotError(f"Os vetores de bins de {expected_name} têm tamanho inválido.")
        parsed_counts = [_count(count, f"bin {expected_name}") for count in counts]
        total = expected_reference_count if name == "referência" else expected_current_count
        if sum(parsed_counts) != total:
            raise DriftSnapshotError(f"As contagens por bin de {expected_name} não fecham o total.")
        parsed = tuple(
            _finite(proportion, f"proporção {expected_name}", minimum=0.0)
            for proportion in proportions
        )
        if any(value > 1.0 for value in parsed) or abs(sum(parsed) - 1.0) > PROPORTION_TOLERANCE:
            raise DriftSnapshotError(
                f"As proporções de {expected_name} não somam aproximadamente 1."
            )
        vectors.append(parsed)

    return FeatureSnapshot(
        feature=expected_name,
        score=score,
        threshold=threshold,
        drift=drift,
        method=method,
        comparison_operator=operator,
        reference_count=reference_count,
        current_count=current_count,
        bin_labels=tuple(labels),
        bin_edges=numeric_edges,
        reference_proportions=vectors[0],
        current_proportions=vectors[1],
    )


def _parse_comparison(raw: Any, expected_id: str) -> ComparisonSnapshot:
    comparison = _object(raw, expected_id)
    if comparison.get("comparison_id") != expected_id:
        raise DriftSnapshotError("A lista de comparações não corresponde ao protocolo.")
    if comparison.get("global_alert_rule") != "any_feature_exceeds_threshold":
        raise DriftSnapshotError("A regra de alerta global não é suportada.")
    method = comparison.get("method")
    if method != "custom_psi":
        raise DriftSnapshotError("O método de comparação não é suportado.")

    reference_rows = _count(comparison.get("reference_rows"), "referência")
    current_rows = _count(comparison.get("current_rows"), "lote")
    raw_features = comparison.get("features")
    if not isinstance(raw_features, list) or len(raw_features) != len(FEATURES):
        raise DriftSnapshotError("A comparação não contém as 19 features financeiras esperadas.")
    features = tuple(
        _parse_feature(item, name, reference_rows, current_rows)
        for item, name in zip(raw_features, FEATURES, strict=True)
    )
    drifted_features = tuple(feature.feature for feature in features if feature.drift)
    declared_drifted = comparison.get("drifted_features")
    drifted_count = _count(comparison.get("drifted_feature_count"), "features sinalizadas")
    global_alert = comparison.get("global_alert")
    if (
        not isinstance(declared_drifted, list)
        or tuple(declared_drifted) != drifted_features
        or drifted_count != len(drifted_features)
        or not isinstance(global_alert, bool)
        or global_alert != bool(drifted_features)
    ):
        raise DriftSnapshotError("O resumo de alertas diverge dos resultados por feature.")
    return ComparisonSnapshot(
        comparison_id=expected_id,
        global_alert=global_alert,
        drifted_feature_count=drifted_count,
        drifted_features=drifted_features,
        method=method,
        reference_rows=reference_rows,
        current_rows=current_rows,
        features=features,
    )


def _parse_predictions(
    summary: dict[str, Any], results: dict[str, Any], name: str, model_sha256: str, threshold: float
) -> PredictionSummary:
    inference = _object(summary.get("inference"), "inference")
    inference_item = _object(inference.get(name), f"inference {name}")
    prediction_groups = _object(summary.get("predictions"), "predictions")
    prediction_item = _object(prediction_groups.get(name), f"predictions {name}")
    _sha256(prediction_item.get("sha256"), f"predições {name}")
    raw_stats = _object(prediction_item.get("summary"), f"summary {name}")
    result_groups = _object(results.get("probability_summaries"), "probability_summaries")
    result_stats = _object(result_groups.get(name), f"probability_summaries {name}")

    if _sha256(inference_item.get("model_sha256"), f"modelo {name}") != model_sha256:
        raise DriftSnapshotError("O hash do modelo diverge entre os resumos congelados.")
    if _finite(inference_item.get("threshold"), f"limiar {name}") != threshold:
        raise DriftSnapshotError("O limiar de inferência diverge entre os resumos congelados.")

    rows = _count(raw_stats.get("rows"), f"linhas {name}")
    positives = _count(raw_stats.get("predicted_positives"), f"previsões classe 1 {name}")
    if rows == 0 or positives > rows:
        raise DriftSnapshotError(f"As contagens de predição de {name} são incompatíveis.")
    if _count(inference_item.get("rows"), f"linhas de inferência {name}") != rows:
        raise DriftSnapshotError("As contagens de inferência divergem dos resumos de scores.")
    if _count(inference_item.get("predicted_positives"), f"classe 1 {name}") != positives:
        raise DriftSnapshotError("As contagens de classe 1 divergem dos resumos de scores.")
    if (
        _count(result_stats.get("rows"), f"linhas do resultado {name}") != rows
        or _count(result_stats.get("predicted_positives"), f"classe 1 do resultado {name}")
        != positives
    ):
        raise DriftSnapshotError("As contagens entre os resumos congelados não coincidem.")

    parsed: dict[str, float] = {}
    for field in ("mean", "median", "p05", "p25", "p75", "p95", "std_population"):
        value = _finite(raw_stats.get(field), f"{field} {name}", minimum=0.0)
        if field != "std_population" and value > 1.0:
            raise DriftSnapshotError(f"O score {field} de {name} está fora do intervalo [0, 1].")
        if not math.isclose(
            value,
            _finite(result_stats.get(field), f"{field} do resultado {name}", minimum=0.0),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise DriftSnapshotError("Os resumos agregados de scores não coincidem.")
        parsed[field] = value
    if not math.isclose(
        parsed["mean"],
        _finite(inference_item.get("mean_probability"), f"média de inferência {name}"),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise DriftSnapshotError("A média de scores diverge entre os resumos congelados.")
    if not (parsed["p05"] <= parsed["p25"] <= parsed["median"] <= parsed["p75"] <= parsed["p95"]):
        raise DriftSnapshotError(f"Os quantis de {name} estão fora de ordem.")

    return PredictionSummary(rows, positives, **parsed)


def load_drift_snapshot(reports_dir: Path) -> DriftSnapshot:
    """Load only the two fixed, versioned JSON snapshots; never reads row-level data."""
    results = _load_json(reports_dir / "drift" / "results-v1.0.2.json")
    predictions = _load_json(reports_dir / "drift" / "prediction_summary-v1.0.2.json")
    _require_versions(results, predictions)

    model_sha256 = _sha256(results.get("model_sha256"), "modelo")
    summary_sha256 = _sha256(predictions.get("model_sha256"), "modelo")
    if model_sha256 != MODEL_SHA256 or summary_sha256 != model_sha256:
        raise DriftSnapshotError(
            "O modelo dos artefatos não corresponde ao cenário congelado 1.0.2."
        )
    threshold = _finite(results.get("threshold_model"), "limiar do modelo", minimum=0.0)
    prediction_threshold = _finite(predictions.get("threshold"), "limiar do resumo")
    if threshold != THRESHOLD or prediction_threshold != threshold:
        raise DriftSnapshotError(
            "O limiar dos artefatos não corresponde ao cenário congelado 1.0.2."
        )
    if results.get("feature_set") != list(FEATURES):
        raise DriftSnapshotError("O conjunto de features dos artefatos não é o esperado.")

    hashes = _object(results.get("hashes"), "hashes")
    input_hashes = _object(predictions.get("input_sha256"), "input_sha256")
    for name in ("original", "modified"):
        results_hash = _sha256(hashes.get(name), f"lote {name}")
        summary_hash = _sha256(input_hashes.get(name), f"lote {name} do resumo")
        if results_hash != summary_hash or results_hash != INPUT_SHA256[name]:
            raise DriftSnapshotError("Os hashes dos lotes não correspondem ao cenário 1.0.2.")
    prediction_summary_path = reports_dir / "drift" / "prediction_summary-v1.0.2.json"
    try:
        actual_summary_hash = hashlib.sha256(prediction_summary_path.read_bytes()).hexdigest()
    except OSError:
        raise DriftSnapshotError(
            "O resumo de predições deixou de estar disponível durante a leitura."
        ) from None
    if _sha256(hashes.get("prediction_summary"), "prediction_summary") != actual_summary_hash:
        raise DriftSnapshotError("O hash do resumo de predições não corresponde ao artefato.")

    raw_comparisons = results.get("comparisons")
    if not isinstance(raw_comparisons, list) or len(raw_comparisons) != len(COMPARISON_IDS):
        raise DriftSnapshotError("O snapshot não contém as três comparações do protocolo.")
    comparisons = tuple(
        _parse_comparison(item, comparison_id)
        for item, comparison_id in zip(raw_comparisons, COMPARISON_IDS, strict=True)
    )
    if comparisons[0].reference_rows != 21_000 or any(
        comparison.current_rows != 4_500 for comparison in comparisons
    ):
        raise DriftSnapshotError("As contagens do cenário 1.0.2 divergem do contrato publicado.")
    expected_drift = ((), ("LIMIT_BAL", "PAY_AMT1"), ("LIMIT_BAL", "PAY_AMT1"))
    if tuple(item.drifted_features for item in comparisons) != expected_drift:
        raise DriftSnapshotError("Os alertas não correspondem ao cenário congelado 1.0.2.")

    original = _parse_predictions(predictions, results, "original", model_sha256, threshold)
    modified = _parse_predictions(predictions, results, "modified", model_sha256, threshold)
    if original.rows != 4_500 or modified.rows != 4_500:
        raise DriftSnapshotError("As contagens de inferência divergem do cenário 1.0.2.")

    return DriftSnapshot(
        scenario_id=SCENARIO_ID,
        protocol_version=PROTOCOL_VERSION,
        schema_version=SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        model_sha256=model_sha256,
        threshold=threshold,
        comparisons=comparisons,
        original=original,
        modified=modified,
    )
