"""Mirror a finalized local execution to the local MLflow experiment."""

import os
from pathlib import Path

from credit_monitoring.monitoring.run_store import Journal


def tracking_uri(root: Path) -> str:
    return f"sqlite:///{(root / 'mlflow.db').as_posix()}"


def publish(journal: Journal, root: Path) -> None:
    tracking = journal.record["tracking"]
    client = None
    try:
        database = root / "mlflow.db"
        if database.exists() and not database.is_file():
            raise IsADirectoryError
        from mlflow import MlflowClient
        from mlflow.exceptions import MlflowException

        client = MlflowClient(tracking_uri=tracking_uri(root))
        name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "credit-scoring-fase-04")
        experiment = client.get_experiment_by_name(name)
        if experiment is None:
            try:
                experiment_id = client.create_experiment(name, (root / "artifacts").as_uri())
            except MlflowException:
                experiment = client.get_experiment_by_name(name)
                if experiment is None:
                    raise
                experiment_id = experiment.experiment_id
        else:
            experiment_id = experiment.experiment_id
        record = journal.record
        run = client.create_run(
            experiment_id,
            tags={
                "execution_id": record["execution_id"],
                "scenario": record["scenario"],
                "execution_status": record["status"],
                "stage": record["stage"] or "unknown",
            },
            run_name=record["execution_id"],
        )
        run_id = tracking["run_id"] = run.info.run_id
        journal.save()
        for key, value in record["provenance"].items():
            if isinstance(value, (str, bool, int, float)):
                client.log_param(run_id, key, value)
        for prefix, values in (
            ("operation", record["counts"] | record["resources"]),
            ("validation", record["model_metrics"].get("validation", {})),
            ("test", record["model_metrics"].get("test", {})),
        ):
            for key, value in values.items():
                if type(value) in (int, float):
                    client.log_metric(run_id, f"{prefix}.{key}", value)
        for feature in (record["drift"] or {}).get("features", []):
            client.log_metric(run_id, f"drift.psi.{feature['feature']}", feature["score"])
        client.log_metric(run_id, "operation.alerts", len(record["alerts"]))
        tracking["status"] = "recorded"
        journal.save()
        for name in ("summary.json", "events.jsonl", "drift.html"):
            path = journal.directory / name
            if path.is_file():
                client.log_artifact(run_id, str(path))
        client.set_terminated(run_id, "FINISHED" if record["status"] == "succeeded" else "FAILED")
    except (Exception, KeyboardInterrupt) as error:
        tracking.update(status="failed", reason=type(error).__name__)
        if client is not None and tracking["run_id"] is not None:
            try:
                client.set_tag(tracking["run_id"], "tracking_status", "failed")
                client.set_terminated(tracking["run_id"], "FAILED")
            except Exception:
                pass
        journal.event("tracking_failed", reason=tracking["reason"])
    finally:
        journal.save()
