"""Execute and record one Phase 3 attempt against the frozen M2 inputs."""

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from credit_monitoring.config import load_config
from credit_monitoring.contracts import ContractViolation, validate_batch
from credit_monitoring.data.loading import file_sha256
from credit_monitoring.data.simulate import protocol_sha256
from credit_monitoring.models.inference import infer_batch, load_model
from credit_monitoring.models.score_production import _probability_summary
from credit_monitoring.monitoring.drift_snapshot import (
    CONTRACT_VERSION,
    INPUT_SHA256,
    MODEL_SHA256,
    SCENARIO_ID,
    THRESHOLD,
    load_drift_snapshot,
)
from credit_monitoring.monitoring.run_store import Journal, Resources, local_root, timestamp
from credit_monitoring.monitoring.tracking import publish, tracking_uri
from credit_monitoring.paths import PROJECT_ROOT

SCENARIOS = ("original", "modified", "invalid", "execution-error")
BATCH_DIR = Path("data/production/v1.0.2")
CONFIG = Path("configs/project.yaml")
MODEL = Path("models/credit_model.joblib")
METADATA = Path("models/credit_model_metadata.json")
REFERENCE = Path("data/reference/reference.csv")
MANIFEST = BATCH_DIR / "manifest.json"
RESULTS = Path("reports/drift/results-v1.0.2.json")
HTML = Path("reports/drift/phase-2-drift-v1.0.2-ptbr-v6.html")
SUMMARY = Path("reports/drift/prediction_summary-v1.0.2.json")
TEST_METRICS = Path("reports/test_metrics.json")

FROZEN = {
    MODEL: MODEL_SHA256,
    REFERENCE: "9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26",
    MANIFEST: "d0e983fa175115e96f508d08512006b23af4e00f3a7f81e4368bd58ded528ee9",
    RESULTS: "f0c02e97fbb3a6301ec1cf65593c9c7977f051bd4c4a2eec7c1276b45ec4bd48",
    HTML: "d47a792b1dfb7d94ee4469ada01298d2bf0e0809e7beda2c4641ae4cf284a451",
    **{BATCH_DIR / f"{key}.csv": digest for key, digest in INPUT_SHA256.items()},
}


class IntegrityError(ValueError):
    """The selected artifact does not belong to the frozen scenario."""


class DemonstrationError(RuntimeError):
    """Controlled failure after a successful contract check."""


def frozen_bytes(project: Path, path: Path) -> bytes:
    payload = (project / path).read_bytes()
    candidates = (
        (payload, payload.replace(b"\r\n", b"\n")) if path in (RESULTS, HTML) else (payload,)
    )
    for candidate in candidates:
        if hashlib.sha256(candidate).hexdigest() == FROZEN[path]:
            return candidate
    raise IntegrityError(path.name)


def git(project: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=project, text=True, stderr=subprocess.DEVNULL, timeout=10
    ).strip()


def locked_report(project: Path, path: Path, stage: str) -> tuple[dict, str, str]:
    lock = yaml.safe_load((project / "dvc.lock").read_text(encoding="utf-8"))
    expected = next(
        item["md5"] for item in lock["stages"][stage]["outs"] if item["path"] == path.as_posix()
    )
    payload = (project / path).read_bytes()
    for candidate in (payload, payload.replace(b"\r\n", b"\n")):
        if hashlib.md5(candidate, usedforsecurity=False).hexdigest() == expected:
            return json.loads(candidate), hashlib.sha256(candidate).hexdigest(), expected
    raise IntegrityError(path.name)


def frozen_model_metrics(metadata: dict, test: dict) -> dict:
    if (
        metadata["model_sha256"] != MODEL_SHA256
        or metadata["contract_version"] != CONTRACT_VERSION
        or metadata["threshold"] != THRESHOLD
    ):
        raise IntegrityError("metadados do modelo")
    if test["model_sha256"] != MODEL_SHA256:
        raise IntegrityError("avaliação congelada")
    selected = metadata["selected_model"]
    candidate = metadata.get("selected_version", {}).get("candidate_id", selected)
    validation = metadata["validation"]
    return {
        "validation": validation.get(candidate, validation[selected]),
        "test": test["test"],
        "validation_source": METADATA.as_posix(),
        "test_source": TEST_METRICS.as_posix(),
        "test_exposure": test["test_exposure"]["declared"],
    }


def execute(project: Path, root: Path, scenario: str) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError("Cenário inválido")
    project, root = project.resolve(), root.resolve()
    journal = Journal(root, scenario)
    record = journal.record
    resources = Resources()
    counts = record["counts"]
    provenance = record["provenance"]
    try:
        with journal.stage("processing"):
            name = "modified" if scenario == "modified" else "original"
            source = BATCH_DIR / f"{name}.csv"
            provenance.update(
                git_sha=git(project, "rev-parse", "HEAD"),
                git_dirty=bool(git(project, "status", "--porcelain")),
                scenario_id=SCENARIO_ID,
                protocol_version="1.0.2",
                contract_version=CONTRACT_VERSION,
                threshold=THRESHOLD,
                source_batch=source.as_posix(),
                source_batch_sha256=FROZEN[source],
                input_kind="invalid_limit_bal" if scenario == "invalid" else "frozen_batch",
                config_sha256=file_sha256(project / CONFIG),
                dvc_lock_sha256=file_sha256(project / "dvc.lock"),
                uv_lock_sha256=file_sha256(project / "uv.lock"),
                scikit_learn_version=version("scikit-learn"),
                pandas_version=version("pandas"),
            )
            payload = frozen_bytes(project, source)
            provenance["source_batch_dvc_md5"] = hashlib.md5(
                payload, usedforsecurity=False
            ).hexdigest()
            frame = pd.read_csv(BytesIO(payload))
            counts["input_rows"] = len(frame)
            counts["inferred_rows"] = 0
            config = load_config(project / CONFIG)
            if scenario == "invalid":
                frame.loc[frame.index[0], "LIMIT_BAL"] = -1

        with journal.stage("validation"):
            validate_batch(frame, config, labeled=False)
            counts.update(accepted_rows=len(frame), rejected_rows=0)

        with journal.stage("inference"):
            if scenario == "execution-error":
                raise DemonstrationError
            manifest = json.loads(frozen_bytes(project, MANIFEST))
            if manifest["protocol_sha256"] != protocol_sha256(config["drift"]):
                raise IntegrityError("configuração do protocolo")
            metadata, metadata_sha, metadata_md5 = locked_report(project, METADATA, "train")
            test, test_sha, test_md5 = locked_report(project, TEST_METRICS, "evaluate")
            provenance.update(
                model_sha256=MODEL_SHA256,
                model=metadata["selected_model"],
                model_version=metadata.get("selected_version", {}).get(
                    "candidate_id", metadata["selected_model"]
                ),
                model_metadata_sha256=metadata_sha,
                model_metadata_dvc_md5=metadata_md5,
                test_metrics_sha256=test_sha,
                test_metrics_dvc_md5=test_md5,
                manifest_sha256=FROZEN[MANIFEST],
            )
            record["model_metrics"] = frozen_model_metrics(metadata, test)
            model = load_model(project / MODEL, expected_sha256=MODEL_SHA256)
            result = infer_batch(
                model,
                frame,
                config,
                features=metadata["features"],
                threshold=THRESHOLD,
                model_sha256=MODEL_SHA256,
            )
            if result.rows != len(frame) or len(result.probability) != len(frame):
                raise IntegrityError("volume de inferência")
            record["inference"] = _probability_summary(result.probability, result.predicted)
            histogram, edges = np.histogram(result.probability, bins=np.linspace(0, 1, 11))
            record["inference"]["histogram"] = {
                "counts": histogram.tolist(),
                "edges": edges.tolist(),
            }
            record["inference"]["predict_proba_s"] = result.duration_s
            counts["inferred_rows"] = result.rows

        with journal.stage("drift"):
            frozen_bytes(project, REFERENCE)
            raw = json.loads(frozen_bytes(project, RESULTS))
            if raw["protocol_sha256"] != manifest["protocol_sha256"]:
                raise IntegrityError("hash do protocolo no snapshot")
            snapshot = load_drift_snapshot(project / "reports")
            comparison = snapshot.comparisons[1 if name == "modified" else 0]
            if comparison.current_rows != result.rows:
                raise IntegrityError("volume M2")
            provenance.update(
                reference_sha256=FROZEN[REFERENCE],
                drift_snapshot_sha256=FROZEN[RESULTS],
                prediction_summary_sha256=raw["hashes"]["prediction_summary"],
                protocol_sha256=raw["protocol_sha256"],
                drift_source="frozen_m2_snapshot",
            )
            if (project / HTML).is_file():
                (journal.directory / "drift.html").write_bytes(frozen_bytes(project, HTML))
                provenance["html_sha256"] = FROZEN[HTML]
            record["drift"] = asdict(comparison)
            if comparison.global_alert:
                for feature in comparison.drifted_features:
                    journal.alert(
                        "data_drift",
                        "warning",
                        "Investigue a mudança de distribuição.",
                        feature=feature,
                    )
        record.update(status="succeeded", reason=None)
    except ContractViolation as error:
        counts.update(accepted_rows=0, rejected_rows=error.rejected_rows, inferred_rows=0)
        record.update(status="rejected", reason="Lote rejeitado integralmente pelo contrato")
        journal.alert(
            "contract_failure",
            "error",
            "Corrija o lote e execute novamente.",
            diagnostics=error.to_dict(),
        )
    except (Exception, KeyboardInterrupt) as error:
        record.update(status="failed", reason=type(error).__name__)
        journal.alert("execution_failure", "error", "Investigue a etapa e os artefatos de entrada.")
    record.update(finished_at=timestamp(), resources=resources.collect())
    journal.event("execution_finished", status=record["status"], reason=record["reason"])
    journal.save()
    publish(journal, root)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=(*SCENARIOS, "tracking-uri"))
    options = parser.parse_args(argv)
    root = local_root()
    if options.scenario == "tracking-uri":
        print(tracking_uri(root))
        return 0
    record = execute(PROJECT_ROOT, root, options.scenario)
    print(
        json.dumps({key: record[key] for key in ("execution_id", "status", "reason", "tracking")})
    )
    if record["status"] == "succeeded":
        return 0 if record["tracking"]["status"] == "recorded" else 3
    return 2 if record["status"] == "rejected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
