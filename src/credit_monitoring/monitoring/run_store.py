"""Local execution journal and process resource measurements."""

import json
import os
import platform
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from credit_monitoring.paths import PROJECT_ROOT

SCHEMA_VERSION = "1.0.0"
STATUSES = {"running", "succeeded", "rejected", "failed"}


def local_root() -> Path:
    return (PROJECT_ROOT / os.environ.get("OBSERVABILITY_DIR", "observability")).resolve()


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def rss_mib() -> float | None:
    try:
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return round(pages * os.sysconf("SC_PAGE_SIZE") / 1024**2, 3)
    except (OSError, ValueError, IndexError):
        return None


def peak_memory() -> tuple[float | None, str]:
    if sys.platform == "win32":
        # psutil is installed with MLflow in the observability environment.
        try:
            import psutil

            return psutil.Process().memory_info().peak_wset / 1024**2, "Windows PeakWorkingSetSize"
        except (ImportError, AttributeError, OSError):
            return None, "PeakWorkingSetSize indisponível"
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        divisor = 1024**2 if sys.platform == "darwin" else 1024
        return peak / divisor, "getrusage(RUSAGE_SELF).ru_maxrss"
    except (ImportError, OSError):
        return None, "getrusage indisponível"


class Resources:
    """Same wall/CPU/RSS fields as training, including failure paths."""

    def __init__(self):
        self.wall = time.perf_counter()
        self.cpu = time.process_time()
        self.rss = rss_mib() if sys.platform.startswith("linux") else None

    def collect(self) -> dict:
        after = rss_mib() if sys.platform.startswith("linux") else None
        peak, method = peak_memory()
        return {
            "wall_time_s": time.perf_counter() - self.wall,
            "cpu_time_s": time.process_time() - self.cpu,
            "rss_before_mib": self.rss,
            "rss_after_mib": after,
            "rss_delta_mib": None if self.rss is None or after is None else after - self.rss,
            "process_peak_rss_mib": peak,
            "peak_memory_unavailable_reason": method if peak is None else None,
            "method": f"perf_counter, process_time, /proc/self/statm (Linux), {method}",
            "platform": platform.platform(),
            "scope": "Processo atual; pico desde o início do processo; sem processos filhos",
        }


class Journal:
    def __init__(self, root: Path, scenario: str):
        execution_id = uuid4().hex
        self.directory = root / "runs" / execution_id
        self.directory.mkdir(parents=True)
        self.record = {
            "schema_version": SCHEMA_VERSION,
            "execution_id": execution_id,
            "scenario": scenario,
            "started_at": timestamp(),
            "finished_at": None,
            "status": "running",
            "stage": None,
            "reason": "Tentativa em curso ou interrompida antes do encerramento",
            "tracking": {"status": "pending", "run_id": None},
            "counts": dict.fromkeys(
                ("input_rows", "accepted_rows", "rejected_rows", "inferred_rows")
            ),
            "resources": {},
            "stages": {},
            "provenance": {},
            "model_metrics": {},
            "inference": None,
            "drift": None,
            "alerts": [],
        }
        self.save()
        self.event("execution_started")

    def save(self):
        temporary = self.directory / "summary.tmp"
        temporary.write_text(
            json.dumps(self.record, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(self.directory / "summary.json")

    def event(self, event: str, **details):
        entry = {
            "execution_id": self.record["execution_id"],
            "at": timestamp(),
            "stage": self.record["stage"],
            "event": event,
            **details,
        }
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @contextmanager
    def stage(self, name: str):
        from credit_monitoring.contracts import ContractViolation

        self.record["stage"] = name
        self.save()
        self.event("stage_started")
        resources = Resources()
        status = "succeeded"
        try:
            yield
        except ContractViolation:
            status = "rejected"
            raise
        except BaseException:
            status = "failed"
            raise
        finally:
            self.record["stages"][name] = {"status": status, **resources.collect()}
            self.event("stage_finished", status=status)
            self.save()

    def alert(self, kind: str, severity: str, message: str, **details):
        alert = {
            "execution_id": self.record["execution_id"],
            "stage": self.record["stage"],
            "type": kind,
            "severity": severity,
            "message": message,
            **details,
        }
        key = (kind, details.get("feature"))
        if all((item["type"], item.get("feature")) != key for item in self.record["alerts"]):
            self.record["alerts"].append(alert)
            self.event("alert", alert=alert)


def load_records(root: Path) -> tuple[list[dict], int]:
    records = []
    incompatible = 0
    for path in (root / "runs").glob("*/summary.json"):
        try:
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError
            record = json.loads(path.read_text(encoding="utf-8"))
            if (
                record["schema_version"] != SCHEMA_VERSION
                or record["execution_id"] != path.parent.name
                or record["status"] not in STATUSES
                or not isinstance(record["scenario"], str)
                or not isinstance(record["alerts"], list)
                or any(
                    not isinstance(alert, dict)
                    or not {"type", "severity", "message"} <= alert.keys()
                    for alert in record["alerts"]
                )
                or not all(
                    isinstance(record[key], dict)
                    for key in ("counts", "resources", "provenance", "tracking", "model_metrics")
                )
            ):
                raise ValueError
            if datetime.fromisoformat(record["started_at"]).utcoffset() is None:
                raise ValueError
            records.append(record)
        except (OSError, ValueError, TypeError, KeyError):
            incompatible += 1
    return sorted(records, key=lambda item: item["started_at"], reverse=True), incompatible
