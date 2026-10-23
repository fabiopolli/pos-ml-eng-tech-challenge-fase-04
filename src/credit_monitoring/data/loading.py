"""Raw dataset loading."""

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from credit_monitoring.config import canonical_columns
from credit_monitoring.paths import RAW_DATA_DIR


def default_raw_path(config: dict[str, Any]) -> Path:
    return RAW_DATA_DIR / config["dataset"]["raw_file"]


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_raw(path: str | Path, config: dict[str, Any]) -> pd.DataFrame:
    """Read the raw CSV, skipping the leading X1..X23/Y line, and rename the target."""
    dataset = config["dataset"]
    raw = pd.read_csv(
        path,
        sep=dataset["csv"]["sep"],
        header=dataset["csv"]["header_row"],
        skipinitialspace=True,
    )
    raw = raw.rename(columns={dataset["target_column_raw"]: dataset["canonical_target"]})
    missing = [column for column in canonical_columns(config) if column not in raw.columns]
    if missing:
        raise ValueError(f"Raw dataset is missing columns: {missing}")
    return raw
