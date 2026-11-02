"""Reference-binned Population Stability Index (PSI) and Evidently HTML reports."""

import argparse
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from credit_monitoring.config import feature_columns, load_config
from credit_monitoring.contracts import validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.monitoring.report_context import build_report_context
from credit_monitoring.paths import DATA_DIR, MODELS_DIR, REPORTS_DIR


class DriftAnalysisError(ValueError):
    """Raised when a comparison is incompatible with the frozen drift protocol."""


def _canonical_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _finite_values(values: pd.Series, name: str) -> np.ndarray:
    array = pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    if array.size == 0 or not np.isfinite(array).all():
        raise DriftAnalysisError(f"Feature {name} is empty or contains non-finite values")
    return array


def _fit_bins(reference: np.ndarray, *, max_bins: int, separate_zero_mass: bool) -> dict[str, Any]:
    nonzero = reference[reference != 0] if separate_zero_mass else reference
    spec: dict[str, Any] = {
        "zero_separate": bool(separate_zero_mass),
        "zero_bin_present": bool(separate_zero_mass),
        "constant_value": None,
        "edges": [],
        "labels": [],
    }
    if nonzero.size == 0:
        if separate_zero_mass:
            spec["labels"] = ["zero", "nonzero"]
            spec["all_zero_reference"] = True
        else:
            spec["labels"] = ["constant", "other"]
            spec["constant_value"] = 0.0
            spec["all_zero_reference"] = False
        return spec

    unique = np.unique(nonzero)
    if unique.size == 1:
        spec["constant_value"] = float(unique[0])
        spec["labels"] = (["zero"] if separate_zero_mass else []) + ["constant", "other"]
        spec["all_zero_reference"] = False
        return spec

    probabilities = np.linspace(0.0, 1.0, max_bins + 1)[1:-1]
    edges = np.unique(np.quantile(nonzero, probabilities)).astype(float)
    spec["edges"] = edges.tolist()
    spec["labels"] = (["zero"] if separate_zero_mass else []) + [
        f"qbin_{index:02d}" for index in range(len(edges) + 1)
    ]
    spec["all_zero_reference"] = False
    return spec


def _bin_counts(values: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    labels = spec["labels"]
    counts = np.zeros(len(labels), dtype=np.int64)
    index = {label: i for i, label in enumerate(labels)}
    zero_mask = values == 0
    if spec["zero_separate"]:
        counts[index["zero"]] = int(zero_mask.sum())
        nonzero = values[~zero_mask]
    else:
        nonzero = values

    if spec["all_zero_reference"]:
        counts[index["nonzero"]] = int(nonzero.size)
    elif spec["constant_value"] is not None:
        equal = nonzero == spec["constant_value"]
        counts[index["constant"]] = int(equal.sum())
        counts[index["other"]] = int((~equal).sum())
    else:
        edges = np.asarray(spec["edges"], dtype=float)
        bins = np.searchsorted(edges, nonzero, side="right")
        offset = 1 if spec["zero_separate"] else 0
        for bin_index in range(len(edges) + 1):
            counts[offset + bin_index] = int((bins == bin_index).sum())
    return counts


def calculate_psi(
    reference: pd.Series | np.ndarray,
    current: pd.Series | np.ndarray,
    *,
    feature: str,
    max_bins: int = 10,
    separate_zero_mass: bool = True,
    smoothing: float = 1e-6,
    threshold: float = 0.20,
) -> dict[str, Any]:
    """Calculate PSI with bins fitted only on the reference and normalized smoothing."""
    ref = _finite_values(pd.Series(reference), feature)
    cur = _finite_values(pd.Series(current), feature)
    if max_bins < 1 or smoothing <= 0 or not np.isfinite(smoothing):
        raise DriftAnalysisError("PSI requires positive bin count and finite positive smoothing")
    spec = _fit_bins(ref, max_bins=max_bins, separate_zero_mass=separate_zero_mass)
    ref_counts = _bin_counts(ref, spec)
    cur_counts = _bin_counts(cur, spec)
    bin_count = len(ref_counts)
    ref_proportions = (ref_counts + smoothing) / (len(ref) + smoothing * bin_count)
    cur_proportions = (cur_counts + smoothing) / (len(cur) + smoothing * bin_count)
    contributions = (cur_proportions - ref_proportions) * np.log(cur_proportions / ref_proportions)
    score = float(contributions.sum())
    return {
        "feature": feature,
        "method": "custom_psi",
        "score": score,
        "threshold": float(threshold),
        "comparison": ">",
        "drift": bool(score > threshold),
        "reference_count": int(len(ref)),
        "current_count": int(len(cur)),
        "reference_bin_counts": ref_counts.tolist(),
        "current_bin_counts": cur_counts.tolist(),
        "reference_proportions": ref_proportions.tolist(),
        "current_proportions": cur_proportions.tolist(),
        "bin_spec": spec,
        "smoothing": float(smoothing),
    }


def _comparison(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    features: list[str],
    protocol: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    psi_config = protocol["psi"]
    results = [
        calculate_psi(
            reference[feature],
            current[feature],
            feature=feature,
            max_bins=int(psi_config["reference_quantile_bins"]),
            separate_zero_mass=bool(psi_config["separate_zero_mass"]),
            smoothing=float(psi_config["smoothing"]),
            threshold=float(psi_config["per_feature_threshold"]),
        )
        for feature in features
    ]
    drifted = [item["feature"] for item in results if item["drift"]]
    return {
        "comparison_id": name,
        "reference_rows": int(len(reference)),
        "current_rows": int(len(current)),
        "method": "custom_psi",
        "global_alert_rule": protocol["psi"]["global_alert"],
        "global_alert": bool(drifted),
        "drifted_feature_count": len(drifted),
        "drifted_features": drifted,
        "features": results,
    }


def _validate_and_select(
    frame: pd.DataFrame, config: dict[str, Any], *, labeled: bool
) -> pd.DataFrame:
    validated = validate_batch(frame, config, labeled=labeled)
    return validated[feature_columns(config)].copy()


def _format_integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _format_decimal(value: float, decimals: int = 3) -> str:
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _feature_label(feature: str) -> str:
    descriptions = {
        "LIMIT_BAL": "Limite de crédito (NT$)",
        "PAY_0": "Status de pagamento (categoria ordinal)",
        "PAY_2": "Status de pagamento (categoria ordinal)",
        "PAY_3": "Status de pagamento (categoria ordinal)",
        "PAY_4": "Status de pagamento (categoria ordinal)",
        "PAY_5": "Status de pagamento (categoria ordinal)",
        "PAY_6": "Status de pagamento (categoria ordinal)",
    }
    if feature.startswith("BILL_AMT"):
        return "Valor da fatura (NT$)"
    if feature.startswith("PAY_AMT"):
        return "Pagamento efetuado (NT$)"
    return descriptions.get(feature, "Variável financeira")


def _comparison_copy(comparison_id: str) -> tuple[str, str]:
    content = {
        "reference_vs_original": (
            "Referência × controle original",
            "Mostra a diferença entre o treino usado como referência e a produção original, "
            "sem as alterações sintéticas. É o controle para contextualizar alertas que já "
            "existiriam antes da intervenção.",
        ),
        "reference_vs_modified": (
            "Referência × cenário modificado",
            "Compara a referência com a cópia em que duas variáveis foram alteradas. "
            "É a comparação principal para verificar se o detector reconhece "
            "as mudanças planejadas.",
        ),
        "original_vs_modified": (
            "Controle original × cenário modificado",
            "Compara as duas versões do mesmo lote de produção. Ajuda a isolar o efeito das "
            "transformações sintéticas, sem substituir a comparação com a referência.",
        ),
    }
    return content.get(comparison_id, (comparison_id, "Comparação entre distribuições."))


def _feature_rows(comparison: dict[str, Any], altered_features: list[str]) -> str:
    rows = []
    for item in comparison["features"]:
        feature = item["feature"]
        drifted = bool(item["drift"])
        score_width = min(max(float(item["score"]), 0.0), 1.0) * 100
        state = "Sinal acima do limite" if drifted else "Sem sinal acima do limite"
        state_class = "alert" if drifted else "ok"
        altered_class = " altered" if feature in altered_features else ""
        change_badge = (
            '<span class="planned-change">alterada no cenário</span>' if altered_class else ""
        )
        threshold_position = float(item["threshold"]) * 100
        feature_cell = (
            '<th scope="row"><span class="feature-label">'
            f"{html.escape(_feature_label(feature))}</span>"
            f"<code>{html.escape(feature)}</code>{change_badge}</th>"
        )
        aria_label = (
            f"PSI {_format_decimal(float(item['score']))}; "
            f"limite {_format_decimal(float(item['threshold']))}"
        )
        rows.append(
            f'<tr class="{altered_class.strip()}">'
            f"{feature_cell}"
            f'<td class="psi-number">{_format_decimal(float(item["score"]))}</td>'
            f'<td><div class="psi-track" role="img" aria-label="{aria_label}">'
            f'<span class="psi-fill {state_class}" style="width:{score_width:.3f}%"></span>'
            f'<span class="psi-threshold" style="left:{threshold_position:.3f}%" '
            'title="Limite de decisão"></span></div>'
            '<div class="axis"><span>0</span><span>limite</span><span>1,0</span></div></td>'
            f"<td>{_format_decimal(float(item['threshold']))}</td>"
            f'<td><span class="badge {state_class}">{state}</span></td>'
            "</tr>"
        )
    return "".join(rows)


def _comparison_sections(comparisons: list[dict[str, Any]], altered_features: list[str]) -> str:
    cards = []
    for index, comparison in enumerate(comparisons):
        title, explanation = _comparison_copy(comparison["comparison_id"])
        altered = comparison["drifted_feature_count"]
        total = len(comparison["features"])
        signal_class = "alert" if comparison["global_alert"] else "ok"
        open_attribute = " open" if comparison["comparison_id"] == "reference_vs_modified" else ""
        alert_label = "Alerta" if comparison["global_alert"] else "Sem alerta"
        reference_count = _format_integer(comparison["reference_rows"])
        current_count = _format_integer(comparison["current_rows"])
        cards.append(
            f'<details class="comparison"{open_attribute}>'
            '<summary><span class="comparison-index">'
            f'0{index + 1}</span><span class="comparison-heading">'
            f"<strong>{html.escape(title)}</strong>"
            f"<small>{altered} de {total} variáveis com sinal</small></span>"
            f'<span class="badge {signal_class}">{alert_label}</span>'
            "</summary>"
            f'<div class="comparison-body"><p>{html.escape(explanation)}</p>'
            f'<p class="sample-size">Amostras comparadas: {reference_count} na referência e '
            f"{current_count} no conjunto comparado.</p>"
            '<div class="table-scroll"><table><thead><tr><th scope="col">Variável</th>'
            '<th scope="col">PSI</th><th scope="col">Escala visual (0–1)</th>'
            '<th scope="col">Limite</th><th scope="col">Leitura</th></tr></thead><tbody>'
            f"{_feature_rows(comparison, altered_features)}</tbody></table></div></div></details>"
        )
    return "".join(cards)


def _probability_section(summaries: dict[str, Any]) -> str:
    labels = {"original": "Controle original", "modified": "Cenário modificado"}
    rows = []
    for scenario in ("original", "modified"):
        summary = summaries[scenario]
        rows.append(
            "<tr>"
            f'<th scope="row">{labels[scenario]}</th>'
            f"<td>{_format_integer(summary['rows'])}</td>"
            f"<td>{_format_decimal(float(summary['mean']), 4)}</td>"
            f"<td>{_format_decimal(float(summary['p05']), 4)}</td>"
            f"<td>{_format_decimal(float(summary['median']), 4)}</td>"
            f"<td>{_format_decimal(float(summary['p95']), 4)}</td>"
            f"<td>{_format_integer(summary['predicted_positives'])}</td>"
            "</tr>"
        )
    return (
        '<div class="table-scroll"><table><thead><tr><th scope="col">Conjunto</th>'
        '<th scope="col">Registros</th><th scope="col">Média</th><th scope="col">5º percentil</th>'
        '<th scope="col">Mediana</th><th scope="col">95º percentil</th>'
        '<th scope="col">Previsões classe 1</th></tr></thead><tbody>'
        + "".join(rows)
        + '</tbody></table></div><p class="note">As probabilidades são resumos '
        "das previsões do modelo; "
        "sem rótulos de produção, não medem acurácia nem degradação de desempenho.</p>"
    )


def _metadata_details(metadata: dict[str, Any]) -> str:
    labels = {
        "scenario_id": "Identificador do cenário",
        "protocol_version": "Versão do protocolo Data Drift",
        "protocol_sha256": "Hash do protocolo (SHA-256)",
        "model_sha256": "Hash do modelo (SHA-256)",
        "contract_version": "Versão do contrato de dados",
        "seed": "Semente registrada",
        "evidently_version": "Versão do Evidently",
        "persisted_probability_decimals": "Casas decimais persistidas para probabilidades",
        "persisted_probability_rounding": "Regra de arredondamento das probabilidades",
        "reference_sha256": "Hash da referência (SHA-256)",
        "validation_sha256": "Hash da validação de origem (SHA-256)",
        "original_sha256": "Hash do lote original (SHA-256)",
        "modified_sha256": "Hash do lote modificado (SHA-256)",
        "manifest_sha256": "Hash do manifesto (SHA-256)",
        "model_training_versions": "Versões do ambiente de treinamento",
        "dataset_summary_sha256": "Hash do resumo estrutural do dataset (SHA-256)",
        "preparation_report_sha256": "Hash do relatório de preparação/split (SHA-256)",
        "training_metrics_sha256": "Hash das métricas de seleção/validação (SHA-256)",
        "test_metrics_sha256": "Hash das métricas do teste (SHA-256)",
        "optimization_manifest_sha256": "Hash do manifesto de treinamento (SHA-256)",
        "optimization_comparison_sha256": "Hash da comparação de promoção (SHA-256)",
    }
    rows = []
    for key, value in sorted(metadata.items()):
        rendered = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            if isinstance(value, dict)
            else str(value)
        )
        rows.append(
            f'<tr><th scope="row">{html.escape(labels.get(key, key))}</th>'
            f"<td><code>{html.escape(rendered)}</code></td></tr>"
        )
    return "".join(rows)


def _evidently_html(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    features: list[str],
    psi_results: list[dict[str, Any]],
    probability_summaries: dict[str, Any],
    metadata: dict[str, Any],
    protocol: dict[str, Any],
    report_context: dict[str, str],
) -> str:
    try:
        import evidently
        from evidently import Report
        from evidently.metrics import RowCount
    except ImportError as error:
        raise DriftAnalysisError(
            "Evidently is required; install the locked phase-2 extra with "
            "`uv sync --dev --locked --extra drift`"
        ) from error

    snapshot = Report(metrics=[RowCount()]).run(
        current_data=current[features], reference_data=reference[features]
    )
    evidently_row_count = int(snapshot.dict()["metrics"][0]["value"])
    if evidently_row_count != len(current):
        raise DriftAnalysisError("Evidently row-count metric differs from the current batch")
    return _render_html_report(
        comparisons=psi_results,
        probability_summaries=probability_summaries,
        metadata=metadata,
        protocol=protocol,
        report_context=report_context,
        evidently_row_count=evidently_row_count,
        evidently_version=evidently.__version__,
    )


def _render_html_report(
    *,
    comparisons: list[dict[str, Any]],
    probability_summaries: dict[str, Any],
    metadata: dict[str, Any],
    protocol: dict[str, Any],
    report_context: dict[str, str],
    evidently_row_count: int,
    evidently_version: str,
) -> str:
    threshold = float(protocol["psi"]["per_feature_threshold"])
    feature_count = len(comparisons[0]["features"])
    control = comparisons[0]
    modified = comparisons[1]
    altered_features = protocol["features_to_shift"]
    detected = len(set(altered_features) & set(modified["drifted_features"]))
    expected = len(altered_features)
    summary_class = "alert" if detected >= expected else "ok"
    alert_sentence = (
        f"O cenário modificado apresentou sinal nas {detected} variáveis alteradas; "
        "o controle original apresentou "
        f"{control['drifted_feature_count']} variável(is) acima do limite."
    )
    transformation_values = {
        "LIMIT_BAL": (
            "multiplicado por "
            f"{_format_decimal(float(protocol['scenario']['limit_bal_multiplier']), 1)}"
        ),
        "PAY_AMT1": (
            "multiplicado por "
            f"{_format_decimal(float(protocol['scenario']['pay_amt1_multiplier']), 1)}; "
            "arredondamento half-to-even e zeros preservados"
        ),
    }
    transformation_items = "".join(
        "<li><code>"
        f"{html.escape(feature)}</code> — "
        f"{html.escape(transformation_values.get(feature, 'alteração sintética configurada'))}"
        "</li>"
        for feature in altered_features
    )
    all_counts = [comparison["current_rows"] for comparison in comparisons]
    reference_rows = comparisons[0]["reference_rows"]
    from string import Template

    rounding = str(metadata["persisted_probability_rounding"])
    rounding_label = "half-to-even (empate para o par)" if rounding == "half_to_even" else rounding
    values = {
        "protocol_version": html.escape(str(metadata["protocol_version"])),
        "summary_class": summary_class,
        "detected": str(detected),
        "expected": str(expected),
        "alert_sentence": html.escape(alert_sentence),
        "control_signals": str(control["drifted_feature_count"]),
        "reference_rows": _format_integer(reference_rows),
        "production_rows": _format_integer(all_counts[0]),
        "feature_count": str(feature_count),
        "transformation_items": transformation_items,
        "threshold": _format_decimal(threshold),
        "comparison_sections": _comparison_sections(comparisons, altered_features),
        "probability_section": _probability_section(probability_summaries),
        "bin_count": str(int(protocol["psi"]["reference_quantile_bins"])),
        "smoothing": _format_decimal(float(protocol["psi"]["smoothing"]), 6),
        "probability_decimals": str(metadata["persisted_probability_decimals"]),
        "probability_rounding": html.escape(rounding_label),
        "evidently_version": html.escape(evidently_version),
        "metadata_details": _metadata_details(metadata),
        "scenario_id": html.escape(str(metadata["scenario_id"])),
        "evidently_row_count": _format_integer(evidently_row_count),
        **report_context,
    }
    template = Path(__file__).with_name("drift_report_template.html").read_text(encoding="utf-8")
    return Template(template).substitute(values)


def run_drift_analysis(
    *,
    reference_path: Path,
    original_path: Path,
    modified_path: Path,
    manifest_path: Path,
    prediction_summary_path: Path,
    model_metadata_path: Path,
    dataset_summary_path: Path,
    preparation_report_path: Path,
    training_metrics_path: Path,
    test_metrics_path: Path,
    optimization_manifest_path: Path,
    optimization_comparison_path: Path,
    results_path: Path,
    report_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prediction_summary = json.loads(prediction_summary_path.read_text(encoding="utf-8"))
    model_metadata = json.loads(model_metadata_path.read_text(encoding="utf-8"))
    dataset_summary = json.loads(dataset_summary_path.read_text(encoding="utf-8"))
    preparation_report = json.loads(preparation_report_path.read_text(encoding="utf-8"))
    training_metrics = json.loads(training_metrics_path.read_text(encoding="utf-8"))
    test_metrics = json.loads(test_metrics_path.read_text(encoding="utf-8"))
    optimization_manifest = json.loads(optimization_manifest_path.read_text(encoding="utf-8"))
    optimization_comparison = json.loads(optimization_comparison_path.read_text(encoding="utf-8"))
    protocol = config["drift"]
    if manifest["protocol_version"] != protocol["protocol_version"]:
        raise DriftAnalysisError("Simulation manifest uses a different drift protocol version")
    if manifest["protocol_sha256"] != _canonical_sha256(protocol):
        raise DriftAnalysisError("Simulation manifest protocol hash differs from current config")
    if prediction_summary["model_sha256"] != model_metadata["model_sha256"]:
        raise DriftAnalysisError("Prediction summary and frozen model metadata do not match")
    if prediction_summary["scenario_id"] != manifest["scenario_id"]:
        raise DriftAnalysisError("Prediction summary belongs to a different scenario")

    reference_frame = pd.read_csv(reference_path)
    original_frame = pd.read_csv(original_path)
    modified_frame = pd.read_csv(modified_path)
    reference = _validate_and_select(reference_frame, config, labeled=True)
    original = _validate_and_select(original_frame, config, labeled=False)
    modified = _validate_and_select(modified_frame, config, labeled=False)
    features = feature_columns(config)
    comparisons = [
        ("reference_vs_original", reference, original),
        ("reference_vs_modified", reference, modified),
        ("original_vs_modified", original, modified),
    ]
    results = []
    for comparison_id, left, right in comparisons:
        comparison = _comparison(
            left, right, features=features, protocol=protocol, name=comparison_id
        )
        results.append(comparison)

    result = {
        "schema_version": "1.0.0",
        "scenario_id": manifest["scenario_id"],
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": manifest["protocol_sha256"],
        "evidently_version": importlib.metadata.version("evidently"),
        "model_sha256": model_metadata["model_sha256"],
        "contract_version": model_metadata["contract_version"],
        "threshold_model": float(model_metadata["threshold"]),
        "hashes": {
            "reference": file_sha256(reference_path),
            "original": file_sha256(original_path),
            "modified": file_sha256(modified_path),
            "manifest": file_sha256(manifest_path),
            "prediction_summary": file_sha256(prediction_summary_path),
        },
        "seed": int(protocol["seed"]),
        "feature_set": features,
        "probability_summaries": {
            key: prediction_summary["predictions"][key]["summary"]
            for key in ["original", "modified"]
        },
        "comparisons": results,
        "limitations": [
            "Validation features were previously used for model selection; "
            "this is not a new holdout.",
            "The interventions are synthetic Data Drift, not a real temporal "
            "shift or Concept Drift.",
            "No labels are present in production batches; no performance degradation is inferred.",
            "PSI is an effect-size measure here, not a p-value; "
            "unused_p_value_alpha is not applied.",
        ],
    }
    report_context = build_report_context(
        dataset_summary=dataset_summary,
        preparation=preparation_report,
        training_metrics=training_metrics,
        test_metrics=test_metrics,
        model_metadata=model_metadata,
        optimization_manifest=optimization_manifest,
        optimization_comparison=optimization_comparison,
        prediction_summary=prediction_summary,
        config=config,
        comparisons=results,
    )
    if results_path.exists():
        existing_result = json.loads(results_path.read_text(encoding="utf-8"))
        if existing_result != result:
            raise DriftAnalysisError(
                "Existing results differ for this scenario; use a new protocol version "
                "instead of overwriting a prior execution"
            )
        if report_path.is_file():
            existing_report = report_path.read_text(encoding="utf-8")
            required_markers = [
                manifest["scenario_id"],
                manifest["protocol_sha256"],
                model_metadata["model_sha256"],
                'data-report-template="pt-BR-5"',
                str(prediction_summary["probability_decimals"]),
                "Referência × controle original",
                "Referência × cenário modificado",
                "Controle original × cenário modificado",
            ]
            if all(marker in existing_report for marker in required_markers):
                return result

    html_report = _evidently_html(
        reference,
        modified,
        features=features,
        psi_results=results,
        probability_summaries={
            key: prediction_summary["predictions"][key]["summary"]
            for key in ["original", "modified"]
        },
        metadata={
            "scenario_id": manifest["scenario_id"],
            "protocol_version": protocol["protocol_version"],
            "protocol_sha256": manifest["protocol_sha256"],
            "model_sha256": model_metadata["model_sha256"],
            "contract_version": model_metadata["contract_version"],
            "seed": protocol["seed"],
            "evidently_version": importlib.metadata.version("evidently"),
            "persisted_probability_decimals": prediction_summary["probability_decimals"],
            "persisted_probability_rounding": prediction_summary["probability_rounding"],
            "model_training_versions": model_metadata["versions"],
            "reference_sha256": file_sha256(reference_path),
            "validation_sha256": manifest["source"]["validation_sha256"],
            "original_sha256": file_sha256(original_path),
            "modified_sha256": file_sha256(modified_path),
            "manifest_sha256": file_sha256(manifest_path),
            "dataset_summary_sha256": file_sha256(dataset_summary_path),
            "preparation_report_sha256": file_sha256(preparation_report_path),
            "training_metrics_sha256": file_sha256(training_metrics_path),
            "test_metrics_sha256": file_sha256(test_metrics_path),
            "optimization_manifest_sha256": file_sha256(optimization_manifest_path),
            "optimization_comparison_sha256": file_sha256(optimization_comparison_path),
        },
        protocol=protocol,
        report_context=report_context,
    )
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_bytes = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    _write_immutable(results_path, results_bytes)
    _write_immutable(report_path, html_report.encode("utf-8"))
    return result


def _write_immutable(path: Path, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    if path.exists():
        if file_sha256(path) != digest:
            raise DriftAnalysisError(
                f"Refusing to overwrite an existing phase-2 analysis result: {path}"
            )
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    production = DATA_DIR / "production/v1.0.2"
    parser.add_argument("--reference", type=Path, default=DATA_DIR / "reference/reference.csv")
    parser.add_argument("--original", type=Path, default=production / "original.csv")
    parser.add_argument("--modified", type=Path, default=production / "modified.csv")
    parser.add_argument("--manifest", type=Path, default=production / "manifest.json")
    parser.add_argument(
        "--prediction-summary",
        type=Path,
        default=REPORTS_DIR / "drift/prediction_summary-v1.0.2.json",
    )
    parser.add_argument(
        "--model-metadata", type=Path, default=MODELS_DIR / "credit_model_metadata.json"
    )
    parser.add_argument(
        "--dataset-summary", type=Path, default=REPORTS_DIR / "eda/eda_summary.json"
    )
    parser.add_argument(
        "--preparation-report", type=Path, default=DATA_DIR / "processed/preparation_report.json"
    )
    parser.add_argument("--training-metrics", type=Path, default=REPORTS_DIR / "metrics.json")
    parser.add_argument("--test-metrics", type=Path, default=REPORTS_DIR / "test_metrics.json")
    optimization = REPORTS_DIR / "optimization/opt-20261026-01"
    parser.add_argument(
        "--optimization-manifest", type=Path, default=optimization / "tuning/manifest.json"
    )
    parser.add_argument(
        "--optimization-comparison",
        type=Path,
        default=optimization / "selection/comparison.json",
    )
    parser.add_argument("--results", type=Path, default=REPORTS_DIR / "drift/results-v1.0.2.json")
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORTS_DIR / "drift/phase-2-drift-v1.0.2-ptbr-v6.html",
    )
    args = parser.parse_args()
    result = run_drift_analysis(
        reference_path=args.reference,
        original_path=args.original,
        modified_path=args.modified,
        manifest_path=args.manifest,
        prediction_summary_path=args.prediction_summary,
        model_metadata_path=args.model_metadata,
        dataset_summary_path=args.dataset_summary,
        preparation_report_path=args.preparation_report,
        training_metrics_path=args.training_metrics,
        test_metrics_path=args.test_metrics,
        optimization_manifest_path=args.optimization_manifest,
        optimization_comparison_path=args.optimization_comparison,
        results_path=args.results,
        report_path=args.report,
        config=load_config(),
    )
    print(
        json.dumps(
            {
                "scenario_id": result["scenario_id"],
                "comparisons": {
                    item["comparison_id"]: item["drifted_features"]
                    for item in result["comparisons"]
                },
                "results": str(args.results),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
