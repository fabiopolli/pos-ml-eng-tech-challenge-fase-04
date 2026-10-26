"""Reconstruct the raw CSV from the original UCI XLS and record its provenance.

The dataset distributed by UCI (ID 350) ships as a legacy ``.xls`` workbook. The
project consumes a semicolon-separated CSV whose first line is the ``X1..X23;Y``
placeholder row. This module makes that conversion a versioned, reproducible
step: it writes the CSV byte-for-byte and records the hashes of both files plus
every read parameter, so the raw data always has a documented provenance trail.

Any hash divergence invalidates the conversion and the command fails.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from credit_monitoring.config import load_config
from credit_monitoring.paths import DATA_DIR, RAW_DATA_DIR, REPORTS_DIR

PROVENANCE_FILE = "acquisition_provenance.json"
DEFAULT_PROVENANCE_PATH = REPORTS_DIR / PROVENANCE_FILE
UTF8_BOM = "﻿"


class AcquisitionError(RuntimeError):
    """Raised when the conversion cannot be proven to reproduce the expected raw file."""


def file_md5(path: str | Path) -> str:
    digest = hashlib.md5()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_xls_path(config: dict[str, Any]) -> Path:
    acquisition = config["dataset"]["acquisition"]
    return DATA_DIR / acquisition["xls_file"]


def placeholder_row(acquisition: dict[str, Any]) -> str:
    """Rebuild the ``X1..X23;Y`` line that the raw CSV carries as its first row."""
    count = int(acquisition["placeholder_columns"])
    return acquisition["sep"].join(["", *[f"X{i}" for i in range(1, count + 1)], "Y"])


def convert_xls_to_csv(xls_path: str | Path, csv_path: str | Path, config: dict[str, Any]) -> Path:
    """Convert the UCI workbook into the raw CSV used by the project."""
    acquisition = config["dataset"]["acquisition"]
    xls_path = Path(xls_path)
    csv_path = Path(csv_path)
    if not xls_path.is_file():
        raise FileNotFoundError(f"Source workbook not found: {xls_path}")

    workbook = pd.ExcelFile(xls_path)
    if acquisition["sheet"] not in workbook.sheet_names:
        raise AcquisitionError(
            f"Sheet {acquisition['sheet']!r} not found in {xls_path.name}; "
            f"available sheets: {workbook.sheet_names}"
        )
    frame = workbook.parse(acquisition["sheet"], header=int(acquisition["header_row"]))
    body = frame.to_csv(
        sep=acquisition["sep"],
        index=False,
        lineterminator=acquisition["lineterminator"],
    )
    header = UTF8_BOM + placeholder_row(acquisition) + acquisition["lineterminator"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes((header + body).encode("utf-8"))
    return csv_path


def _verify(actual: str, expected: str | None, label: str) -> None:
    if expected and actual != expected:
        raise AcquisitionError(
            f"{label} diverged: got {actual}, expected {expected}. "
            "The conversion no longer reproduces the recorded raw file."
        )


def acquire_dataset(
    xls_path: str | Path,
    csv_path: str | Path,
    config: dict[str, Any],
    *,
    provenance_path: str | Path = DEFAULT_PROVENANCE_PATH,
) -> dict[str, Any]:
    """Rebuild the raw CSV and write the provenance record; fails on hash divergence."""
    acquisition = config["dataset"]["acquisition"]
    xls_path = Path(xls_path)
    csv_path = Path(csv_path)

    source_md5 = file_md5(xls_path)
    _verify(source_md5, acquisition.get("expected_xls_md5"), "Source workbook md5")

    convert_xls_to_csv(xls_path, csv_path, config)

    output_md5 = file_md5(csv_path)
    output_sha256 = file_sha256(csv_path)
    _verify(output_md5, acquisition.get("expected_csv_md5"), "Raw CSV md5")
    _verify(output_sha256, acquisition.get("expected_csv_sha256"), "Raw CSV sha256")

    raw = pd.read_csv(csv_path, sep=acquisition["sep"], header=int(acquisition["header_row"]))
    provenance = {
        "source": {
            "file": xls_path.name,
            "md5": source_md5,
            "sha256": file_sha256(xls_path),
            "size_bytes": xls_path.stat().st_size,
            "repository": "UCI Machine Learning Repository",
            "dataset_id": 350,
            "source_url": acquisition["source_url"],
            "doi": acquisition["doi"],
            "license": acquisition["license"],
            "citation": acquisition["citation"],
        },
        "conversion": {
            "script": "credit_monitoring.data.acquire",
            "sheet": acquisition["sheet"],
            "header_row": int(acquisition["header_row"]),
            "sep": acquisition["sep"],
            "index": False,
            "lineterminator": acquisition["lineterminator"],
            "encoding": "utf-8 with BOM",
            "placeholder_row": placeholder_row(acquisition),
        },
        "output": {
            "file": csv_path.name,
            "md5": output_md5,
            "sha256": output_sha256,
            "size_bytes": csv_path.stat().st_size,
            "rows": int(raw.shape[0]),
            "columns": int(raw.shape[1]),
        },
    }
    provenance_path = Path(provenance_path)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstitui o CSV bruto a partir do XLS original da UCI e registra a proveniencia."
        )
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--xls", default=None)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--provenance", default=str(DEFAULT_PROVENANCE_PATH))
    args = parser.parse_args(argv)

    config = load_config(args.config)
    csv_path = Path(args.csv) if args.csv else RAW_DATA_DIR / config["dataset"]["raw_file"]
    provenance = acquire_dataset(
        args.xls or default_xls_path(config),
        csv_path,
        config,
        provenance_path=args.provenance,
    )
    print(
        f"Bruto reconstruido: {provenance['output']['file']} "
        f"(sha256={provenance['output']['sha256']}, rows={provenance['output']['rows']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
