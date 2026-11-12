import hashlib
import json
from types import SimpleNamespace

import joblib
import pytest
import yaml
from conftest import RAW_TARGET, make_raw
from sklearn.dummy import DummyClassifier

from credit_monitoring.monitoring import observe
from credit_monitoring.monitoring.drift_snapshot import ComparisonSnapshot, FeatureSnapshot
from credit_monitoring.monitoring.tracking import tracking_uri
from credit_monitoring.paths import PROJECT_ROOT


@pytest.fixture
def project(tmp_path, monkeypatch, config):
    def write(relative, payload):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()

    frame = make_raw(config, rows=12).drop(columns=RAW_TARGET)
    model_file = tmp_path / "fixture.joblib"
    model = DummyClassifier(strategy="prior").fit(
        frame[config["dataset"]["financial_features"]], [0, 1] * 6
    )
    joblib.dump(model, model_file)
    model_sha = write(observe.MODEL, model_file.read_bytes())
    protocol = {"protocol_sha256": observe.protocol_sha256(config["drift"])}
    frozen = {
        observe.MODEL: model_sha,
        observe.REFERENCE: write(observe.REFERENCE, b"synthetic reference"),
        observe.MANIFEST: write(observe.MANIFEST, json.dumps(protocol).encode()),
        observe.RESULTS: write(
            observe.RESULTS,
            json.dumps({"hashes": {"prediction_summary": "fixture"}, **protocol}).encode(),
        ),
        observe.HTML: write(observe.HTML, b"<p>Synthetic report</p>"),
    }
    for name, values in (
        ("original", frame),
        ("modified", frame.assign(LIMIT_BAL=frame.LIMIT_BAL * 2)),
    ):
        path = observe.BATCH_DIR / f"{name}.csv"
        frozen[path] = write(path, values.to_csv(index=False).encode())
    write(observe.CONFIG, yaml.safe_dump(config).encode())
    write("uv.lock", b"fixture")
    reports = {
        "train": (
            observe.METADATA,
            {
                "model_sha256": model_sha,
                "contract_version": observe.CONTRACT_VERSION,
                "threshold": observe.THRESHOLD,
                "selected_model": "dummy",
                "features": config["dataset"]["financial_features"],
                "validation": {"dummy": {"roc_auc": 0.5}},
            },
        ),
        "evaluate": (
            observe.TEST_METRICS,
            {
                "model_sha256": model_sha,
                "test": {"roc_auc": 0.5},
                "test_exposure": {"declared": True},
            },
        ),
    }
    stages = {}
    for stage, (path, report) in reports.items():
        payload = json.dumps(report).encode()
        write(path, payload)
        stages[stage] = {
            "outs": [
                {
                    "path": path.as_posix(),
                    "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
                }
            ]
        }
    write("dvc.lock", yaml.safe_dump({"stages": stages}).encode())
    features = tuple(
        FeatureSnapshot(name, 0.5, 0.2, True, "PSI", ">", 12, 12, (), (), (), ())
        for name in ("LIMIT_BAL", "PAY_AMT1")
    )
    comparisons = (
        ComparisonSnapshot("reference_vs_original", False, 0, (), "PSI", 12, 12, ()),
        ComparisonSnapshot(
            "reference_vs_modified", True, 2, ("LIMIT_BAL", "PAY_AMT1"), "PSI", 12, 12, features
        ),
    )
    monkeypatch.setattr(observe, "FROZEN", frozen)
    monkeypatch.setattr(observe, "MODEL_SHA256", model_sha)
    monkeypatch.setattr(observe, "git", lambda _, *args: "abc123" if args[0] == "rev-parse" else "")
    monkeypatch.setattr(
        observe, "load_drift_snapshot", lambda _: SimpleNamespace(comparisons=comparisons)
    )
    return tmp_path


def test_frozen_git_reports_match_published_checksums():
    for path in (observe.RESULTS, observe.HTML):
        assert observe.frozen_bytes(PROJECT_ROOT, path)
    assert observe.locked_report(PROJECT_ROOT, observe.TEST_METRICS, "evaluate")[0]["test"]


def test_scenarios_and_dashboard(project, monkeypatch):
    mlflow = pytest.importorskip("mlflow")
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    root = project / "observability"
    monkeypatch.setenv("OBSERVABILITY_DIR", str(root))
    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard/app.py"))
    app.run()
    assert "Nenhuma execução" in app.info[0].value
    assert not root.exists()
    records = []
    for scenario, status, alerts, counts in (
        ("original", "succeeded", [], (12, 12, 0, 12)),
        ("modified", "succeeded", ["data_drift", "data_drift"], (12, 12, 0, 12)),
        ("invalid", "rejected", ["contract_failure"], (12, 0, 12, 0)),
        ("execution-error", "failed", ["execution_failure"], (12, 12, 0, 0)),
    ):
        record = observe.execute(project, root, scenario)
        records.append(record)
        assert record["status"] == status, record
        assert [alert["type"] for alert in record["alerts"]] == alerts
        assert tuple(record["counts"].values()) == counts
        assert record["resources"]["cpu_time_s"] >= 0
        assert record["tracking"]["status"] == "recorded", record["tracking"]
        directory = root / "runs" / record["execution_id"]
        events = [
            json.loads(line)
            for line in (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert all(event["execution_id"] == record["execution_id"] for event in events)
        assert events[-1]["status"] == status
        client = mlflow.MlflowClient(tracking_uri=tracking_uri(root))
        run_id = record["tracking"]["run_id"]
        run = client.get_run(run_id)
        assert run.info.status == ("FINISHED" if status == "succeeded" else "FAILED")
        assert run.data.tags["execution_status"] == status
        assert "summary.json" in [artifact.path for artifact in client.list_artifacts(run_id)]
        app.run()
        assert not app.exception
        app.selectbox[0].set_value(record["execution_id"]).run()
        assert not app.exception
        assert any(f"{len(alerts)} ocorrência" in item.value for item in app.caption)
    assert len({record["execution_id"] for record in records}) == 4
    assert not records[2]["inference"] and "inference" not in records[2]["stages"]
    assert not records[3]["drift"]
    assert len(list((root / "runs").glob("*/summary.json"))) == 4


def test_tracking_failure_preserves_primary_failure(project):
    pytest.importorskip("mlflow")
    root = project / "broken"
    root.mkdir()
    (root / "mlflow.db").mkdir()
    record = observe.execute(project, root, "execution-error")
    assert record["status"] == "failed"
    assert record["reason"] == "DemonstrationError"
    assert record["tracking"]["status"] == "failed"
    path = root / "runs" / record["execution_id"] / "summary.json"
    assert json.loads(path.read_text(encoding="utf-8")) == record


def test_corrupt_artifact_stops_before_inference(project):
    pytest.importorskip("mlflow")
    (project / observe.BATCH_DIR / "original.csv").write_bytes(b"unexpected bytes")
    record = observe.execute(project, project / "runs-local", "original")
    assert record["status"] == "failed"
    assert record["reason"] == "IntegrityError"
    assert record["counts"]["input_rows"] is None
    assert "inference" not in record["stages"]
