"""Build immutable production-control and synthetic-drift batches for phase 2."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from credit_monitoring.config import load_config
from credit_monitoring.contracts import validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.paths import DATA_DIR, MODELS_DIR


class SimulationError(ValueError):
    """Raised when the M1 inputs or a generated scenario violate the frozen protocol."""


def protocol_sha256(protocol: dict[str, Any]) -> str:
    payload = json.dumps(protocol, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _write_immutable(path: Path, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    if path.exists():
        if file_sha256(path) != digest:
            raise SimulationError(
                f"Refusing to overwrite an existing phase-2 artifact with different content: {path}"
            )
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return digest


def prepare_production_batches(
    validation: pd.DataFrame,
    reference: pd.DataFrame,
    config: dict[str, Any],
    *,
    validation_sha256: str,
    expected_validation_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return target-free original and modified copies, refusing incompatible M1 inputs."""
    if validation_sha256 != expected_validation_sha256:
        raise SimulationError(
            "Validation input hash differs from the frozen model metadata: "
            f"{validation_sha256} != {expected_validation_sha256}"
        )

    validated_validation = validate_batch(validation, config, labeled=True)
    validated_reference = validate_batch(reference, config, labeled=True)
    id_column = config["dataset"]["id_column"]
    target = config["dataset"]["canonical_target"]
    reference_ids = set(validated_reference[id_column].astype(int))
    production_ids = set(validated_validation[id_column].astype(int))
    overlap = reference_ids.intersection(production_ids)
    if overlap:
        raise SimulationError(
            f"Reference and validation share {len(overlap)} IDs; production batch rejected"
        )

    original = validated_validation.drop(columns=[target]).copy(deep=True)
    modified = apply_scenario(original, config)
    if target in original.columns or target in modified.columns:
        raise SimulationError("Production batches must not contain the target")
    return original, modified


def apply_scenario(original: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Apply the frozen deterministic interventions without mutating the input."""
    drift = config["drift"]
    scenario = drift["scenario"]
    if scenario["rounding"] != "half_to_even":
        raise SimulationError(f"Unsupported rounding rule: {scenario['rounding']}")
    limit_column, payment_column = drift["features_to_shift"]
    modified = original.copy(deep=True)
    positive_payment = original[payment_column] > 0

    for column, key in (
        (limit_column, "limit_bal_multiplier"),
        (payment_column, "pay_amt1_multiplier"),
    ):
        if column not in modified:
            raise SimulationError(f"Required intervention feature is missing: {column}")
        multiplier = float(scenario[key])
        transformed = np.rint(modified[column].to_numpy(dtype=float) * multiplier)
        if not np.isfinite(transformed).all():
            raise SimulationError(f"Intervention generated non-finite values in {column}")
        if pd.api.types.is_integer_dtype(modified[column].dtype):
            transformed = transformed.astype(modified[column].dtype)
        modified[column] = transformed

    if scenario.get("preserve_pay_amt1_zeros", False):
        minimum = int(scenario["positive_pay_amt1_minimum"])
        modified.loc[positive_payment, payment_column] = np.maximum(
            modified.loc[positive_payment, payment_column].to_numpy(), minimum
        )

    if not (modified[limit_column] > 0).all():
        raise SimulationError("The LIMIT_BAL intervention must remain strictly positive")
    if scenario.get("preserve_pay_amt1_zeros", False):
        before_zero = original[payment_column].eq(0)
        after_zero = modified[payment_column].eq(0)
        if not before_zero.equals(after_zero):
            raise SimulationError("PAY_AMT1 zero values must remain zero under the intervention")

    validate_batch(modified, config, labeled=False)
    changed = [column for column in original if not original[column].equals(modified[column])]
    expected = [limit_column, payment_column]
    if set(changed) != set(expected):
        raise SimulationError(
            f"Intervention changed {changed}, but exactly {expected} were declared"
        )
    if len(original) != len(modified) or not original.index.equals(modified.index):
        raise SimulationError("Scenario transformation changed row count or order")
    return modified


def build_manifest(
    original: pd.DataFrame,
    modified: pd.DataFrame,
    config: dict[str, Any],
    *,
    validation_sha256: str,
    reference_sha256: str,
    original_sha256: str,
    modified_sha256: str,
) -> dict[str, Any]:
    drift = config["drift"]
    dataset = config["dataset"]
    id_column = dataset["id_column"]
    protocol = drift
    return {
        "schema_version": "1.0.0",
        "scenario_id": f"phase-2-{drift['protocol_version']}",
        "protocol_version": drift["protocol_version"],
        "protocol_sha256": protocol_sha256(protocol),
        "seed": int(drift["seed"]),
        "source": {
            "validation_sha256": validation_sha256,
            "reference_sha256": reference_sha256,
            "rows": int(len(original)),
            "source_split": "validation",
            "validation_used_for_model_selection": True,
        },
        "batches": {
            "original": {"path": "original.csv", "sha256": original_sha256},
            "modified": {"path": "modified.csv", "sha256": modified_sha256},
        },
        "id_column": id_column,
        "id_unique": bool(original[id_column].is_unique),
        "interventions": {
            "LIMIT_BAL": {
                "operation": "multiply_then_round",
                "multiplier": float(drift["scenario"]["limit_bal_multiplier"]),
                "rounding": drift["scenario"]["rounding"],
            },
            "PAY_AMT1": {
                "operation": "multiply_then_round",
                "multiplier": float(drift["scenario"]["pay_amt1_multiplier"]),
                "rounding": drift["scenario"]["rounding"],
                "zeros_preserved": bool(drift["scenario"]["preserve_pay_amt1_zeros"]),
                "minimum_for_originally_positive_values": int(
                    drift["scenario"]["positive_pay_amt1_minimum"]
                ),
            },
            "seed_used_for_random_sampling": False,
        },
        "interpretation": (
            "Deterministic synthetic Data Drift intervention; not an observed time shift, "
            "Concept Drift, or evidence of real performance degradation."
        ),
    }


def run_simulation(
    *,
    validation_path: Path,
    reference_path: Path,
    metadata_path: Path,
    original_path: Path,
    modified_path: Path,
    manifest_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    validation_hash = file_sha256(validation_path)
    reference_hash = file_sha256(reference_path)
    validation = pd.read_csv(validation_path)
    reference = pd.read_csv(reference_path)
    original, modified = prepare_production_batches(
        validation,
        reference,
        config,
        validation_sha256=validation_hash,
        expected_validation_sha256=metadata["validation_sha256"],
    )
    original_bytes = _csv_bytes(original)
    modified_bytes = _csv_bytes(modified)
    original_hash = _write_immutable(original_path, original_bytes)
    modified_hash = _write_immutable(modified_path, modified_bytes)
    manifest = build_manifest(
        original,
        modified,
        config,
        validation_sha256=validation_hash,
        reference_sha256=reference_hash,
        original_sha256=original_hash,
        modified_sha256=modified_hash,
    )
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_immutable(manifest_path, manifest_bytes)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", type=Path, default=DATA_DIR / "processed/validation.csv")
    parser.add_argument("--reference", type=Path, default=DATA_DIR / "reference/reference.csv")
    parser.add_argument("--metadata", type=Path, default=MODELS_DIR / "credit_model_metadata.json")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR / "production/v1.0.2")
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir
    manifest_path = args.manifest or output_dir / "manifest.json"
    manifest = run_simulation(
        validation_path=args.validation,
        reference_path=args.reference,
        metadata_path=args.metadata,
        original_path=output_dir / "original.csv",
        modified_path=output_dir / "modified.csv",
        manifest_path=manifest_path,
        config=load_config(),
    )
    print(
        json.dumps(
            {
                "scenario_id": manifest["scenario_id"],
                "rows": manifest["source"]["rows"],
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
