"""Project configuration loading."""

from pathlib import Path
from typing import Any

import yaml

from credit_monitoring.paths import DEFAULT_CONFIG_PATH


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")
    return config


def feature_columns(config: dict[str, Any]) -> list[str]:
    """Features used by the model (governance features are excluded on purpose)."""
    return list(config["dataset"]["financial_features"])


def canonical_columns(config: dict[str, Any]) -> list[str]:
    dataset = config["dataset"]
    return [
        dataset["id_column"],
        *dataset["financial_features"],
        *dataset["governance_features"],
        dataset["canonical_target"],
    ]
