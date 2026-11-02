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


def _psi_sections(comparisons: list[dict[str, Any]]) -> str:
    sections = []
    for comparison in comparisons:
        rows = []
        for item in comparison["features"]:
            status = "DRIFT" if item["drift"] else "sem sinal"
            rows.append(
                "<tr>"
                f"<td>{html.escape(item['feature'])}</td>"
                f"<td>{item['score']:.6f}</td>"
                f"<td>{item['threshold']:.2f}</td>"
                f"<td>{html.escape(status)}</td>"
                f"<td>{item['reference_count']}</td>"
                f"<td>{item['current_count']}</td>"
                "</tr>"
            )
        sections.append(
            f"<section><h2>PSI results — {html.escape(comparison['comparison_id'])}</h2>"
            "<p>Custom PSI; bins fit on the comparison reference only. "
            "Alert rule: score &gt; threshold.</p>"
            "<table><thead><tr><th>Feature</th><th>PSI</th><th>Threshold</th><th>Result</th>"
            "<th>Reference n</th><th>Current n</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></section>"
        )
    return "".join(sections)


def _probability_table(summaries: dict[str, Any]) -> str:
    rows = []
    for scenario, summary in summaries.items():
        rows.append(
            "<tr>"
            f"<td>{html.escape(scenario)}</td>"
            f"<td>{summary['rows']}</td>"
            f"<td>{summary['mean']:.6f}</td>"
            f"<td>{summary['p05']:.6f}</td>"
            f"<td>{summary['median']:.6f}</td>"
            f"<td>{summary['p95']:.6f}</td>"
            f"<td>{summary['predicted_positives']}</td>"
            "</tr>"
        )
    return (
        "<section><h2>Predicted probability summaries</h2>"
        "<table><thead><tr><th>Scenario</th><th>Rows</th><th>Mean</th><th>P05</th>"
        "<th>Median</th><th>P95</th><th>Positive predictions</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def _metadata_table(metadata: dict[str, Any]) -> str:
    rows = []
    for key, value in sorted(metadata.items()):
        rendered_value = (
            json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)
        )
        rows.append(f"<tr><th>{html.escape(key)}</th><td>{html.escape(rendered_value)}</td></tr>")
    return (
        "<section><h2>Provenance and protocol</h2><table><tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def _evidently_html(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    features: list[str],
    psi_results: list[dict[str, Any]],
    probability_summaries: dict[str, Any],
    metadata: dict[str, Any],
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

    report_metadata = {
        key: value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        for key, value in metadata.items()
    }
    snapshot = Report(metrics=[RowCount()], metadata=report_metadata).run(
        current_data=current[features], reference_data=reference[features]
    )
    html_report = snapshot.get_html_str(as_iframe=False)
    custom = (
        "<section><h1>Phase 2 — Data Drift</h1>"
        "<p>Evidently supplies the HTML report container and row-count context. "
        "The PSI tables below are the canonical custom detector results; no native "
        "Evidently drift test is used.</p></section>"
        + _metadata_table(metadata)
        + _psi_sections(psi_results)
        + _probability_table(probability_summaries)
        + "<section><h2>Interpretation limits</h2><ul>"
        "<li>Validation data was previously used for model selection; it is not a new holdout.</li>"
        "<li>Synthetic feature changes do not establish Concept Drift "
        "or real performance loss.</li>"
        "<li>Predictions are summarized only; no labels are present to calculate performance.</li>"
        "</ul></section>"
    )
    if "</body>" not in html_report:
        raise DriftAnalysisError("Evidently HTML structure lacks a document body")
    html_report = html_report.replace("</body>", f"{custom}</body>")
    return (
        "<!-- Generated with Evidently "
        + html.escape(evidently.__version__)
        + " -->\n"
        + html_report
    )


def run_drift_analysis(
    *,
    reference_path: Path,
    original_path: Path,
    modified_path: Path,
    manifest_path: Path,
    prediction_summary_path: Path,
    model_metadata_path: Path,
    results_path: Path,
    report_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prediction_summary = json.loads(prediction_summary_path.read_text(encoding="utf-8"))
    model_metadata = json.loads(model_metadata_path.read_text(encoding="utf-8"))
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
                "persisted_probability_decimals",
                str(prediction_summary["probability_decimals"]),
                "reference_vs_original",
                "reference_vs_modified",
                "original_vs_modified",
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
        },
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
    parser.add_argument("--results", type=Path, default=REPORTS_DIR / "drift/results-v1.0.2.json")
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORTS_DIR / "drift/phase-2-drift-v1.0.2-final.html",
    )
    args = parser.parse_args()
    result = run_drift_analysis(
        reference_path=args.reference,
        original_path=args.original,
        modified_path=args.modified,
        manifest_path=args.manifest,
        prediction_summary_path=args.prediction_summary,
        model_metadata_path=args.model_metadata,
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
