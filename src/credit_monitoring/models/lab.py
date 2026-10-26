"""Artifact catalog of the model laboratory (plan 1.6, package ``1.6-O6``).

The catalog is the **read-only** view of the artifacts produced by the project:
the published model, the two serialized controls and the finalists frozen by the
optimization campaign. Every entry carries its identity (algorithm, candidate id,
experiment id, role) and its provenance (SHA-256 of the artifact), so the
laboratory can show *which* model produced a number instead of only the number.

The catalog never trains, never promotes and never writes over a dataset, a
metric or the DVC lock. A missing or incompatible artifact is reported as such.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from credit_monitoring.data.loading import file_sha256
from credit_monitoring.models.metrics import THRESHOLD


@dataclass
class ModelEntry:
    """One selectable model of the laboratory."""

    key: str
    label: str
    algorithm: str
    version: str
    role: str
    path: Path
    sha256: str | None = None
    available: bool = False
    error: str | None = None
    features: list[str] = field(default_factory=list)
    threshold: float = THRESHOLD
    experiment_id: str | None = None
    candidate_id: str | None = None
    published: bool = False
    source: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "algorithm": self.algorithm,
            "version": self.version,
            "role": self.role,
            "path": str(self.path),
            "sha256": self.sha256,
            "available": self.available,
            "error": self.error,
            "features": list(self.features),
            "threshold": self.threshold,
            "experiment_id": self.experiment_id,
            "candidate_id": self.candidate_id,
            "published": self.published,
            "source": self.source,
        }


@dataclass
class Catalog:
    """Everything the laboratory may show, plus what is missing."""

    models: list[ModelEntry] = field(default_factory=list)
    published: ModelEntry | None = None
    decision: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    finalists: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    experiment_id: str | None = None

    def by_key(self, key: str) -> ModelEntry | None:
        for entry in self.models:
            if entry.key == key:
                return entry
        return None

    def available_models(self) -> list[ModelEntry]:
        return [entry for entry in self.models if entry.available]


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def discover(
    *,
    models_dir: str | Path,
    reports_dir: str | Path,
    experiment_id: str | None = None,
    features: list[str] | None = None,
) -> Catalog:
    """Build the catalog from the artifacts on disk.

    Nothing is written and nothing is fitted: a missing file becomes an entry
    marked as unavailable, with the reason.
    """
    models_dir = Path(models_dir)
    reports_dir = Path(reports_dir)
    catalog = Catalog()

    metadata = _read_json(models_dir / "credit_model_metadata.json")
    if metadata is None:
        catalog.errors.append(
            f"Metadados do modelo publicados ausentes ou ilegiveis: "
            f"{models_dir / 'credit_model_metadata.json'}"
        )
    comparison = None
    finalists = None
    manifest = None
    if experiment_id:
        catalog.experiment_id = experiment_id
        selection_dir = reports_dir / "optimization" / experiment_id / "selection"
        tuning_dir = reports_dir / "optimization" / experiment_id / "tuning"
        comparison = _read_json(selection_dir / "comparison.json")
        finalists = _read_json(tuning_dir / "finalists.json")
        manifest = _read_json(tuning_dir / "manifest.json")
        if comparison is None:
            catalog.errors.append(
                f"Relatorio de comparacao da campanha ausente: {selection_dir / 'comparison.json'}"
            )
    catalog.comparison = comparison
    catalog.finalists = finalists
    catalog.manifest = manifest
    catalog.decision = (comparison or {}).get("decision")

    feature_list = list(features or [])
    if not feature_list and metadata:
        feature_list = list(metadata.get("features", []))

    entries: list[ModelEntry] = []
    seen: set[str] = set()

    if metadata:
        selected_version = metadata.get("selected_version", {}) or {}
        published_key = selected_version.get("candidate_id") or metadata.get("selected_model")
        for key, record in (metadata.get("candidates") or {}).items():
            if key in seen:
                continue
            seen.add(key)
            path = models_dir / record["path"]
            entry = ModelEntry(
                key=key,
                label=f"{key} ({record.get('version', 'control')})",
                algorithm=key.replace("_finalist", ""),
                version=record.get("version", "control"),
                role=record.get("role", "candidate"),
                path=path,
                sha256=record.get("sha256"),
                features=feature_list,
                threshold=float(metadata.get("threshold", THRESHOLD)),
                experiment_id=selected_version.get("experiment_id"),
                candidate_id=key,
                published=key == published_key,
            )
            _check_artifact(entry, record.get("sha256"))
            entries.append(entry)

    if finalists and experiment_id:
        for algorithm, record in (finalists.get("finalists") or {}).items():
            key = f"{algorithm}_finalist"
            if key in seen:
                continue
            seen.add(key)
            path = models_dir / "optimization" / experiment_id / record["artifact"]
            entry = ModelEntry(
                key=key,
                label=f"{key} ({record.get('feature_variant', 'base')})",
                algorithm=algorithm,
                version=record.get("feature_variant", "base"),
                role="finalist",
                path=path,
                sha256=record.get("sha256"),
                features=feature_list,
                threshold=float(finalists.get("threshold", THRESHOLD)),
                experiment_id=experiment_id,
                candidate_id=key,
                source="optimization",
            )
            _check_artifact(entry, record.get("sha256"))
            entries.append(entry)

    catalog.models = entries
    catalog.published = next((entry for entry in entries if entry.published), None)
    return catalog


def _check_artifact(entry: ModelEntry, expected_sha256: str | None) -> None:
    """Check that the artifact exists and matches the recorded hash."""
    if not entry.path.is_file():
        entry.available = False
        entry.error = f"Artefato ausente: {entry.path}"
        return
    try:
        digest = file_sha256(entry.path)
    except OSError as error:
        entry.available = False
        entry.error = f"Artefato ilegivel: {error}"
        return
    if expected_sha256 and digest != expected_sha256:
        entry.available = False
        entry.error = f"Hash divergente: {digest} != {expected_sha256}"
        return
    entry.sha256 = digest
    entry.available = True
    entry.error = None
