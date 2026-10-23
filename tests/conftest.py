import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from credit_monitoring.config import load_config

RAW_TARGET = "default payment next month"


@pytest.fixture
def config() -> dict:
    config = copy.deepcopy(load_config())
    config["modeling"]["random_forest"].update({"n_estimators": 20, "n_jobs": 1})
    return config


def make_raw(config: dict, rows: int = 600, seed: int = 0) -> pd.DataFrame:
    """Synthetic frame with the same columns as the raw CSV."""
    rng = np.random.default_rng(seed)
    dataset = config["dataset"]
    pay_0 = rng.integers(-2, 4, rows)
    frame = pd.DataFrame(
        {
            dataset["id_column"]: np.arange(1, rows + 1),
            "LIMIT_BAL": rng.integers(1, 50, rows) * 10_000,
            "SEX": rng.integers(1, 3, rows),
            "EDUCATION": rng.integers(1, 5, rows),
            "MARRIAGE": rng.integers(1, 4, rows),
            "AGE": rng.integers(21, 70, rows),
            "PAY_0": pay_0,
        }
    )
    for column in ["PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]:
        frame[column] = rng.integers(-2, 4, rows)
    for index in range(1, 7):
        frame[f"BILL_AMT{index}"] = rng.integers(-1_000, 100_000, rows)
        frame[f"PAY_AMT{index}"] = rng.integers(0, 20_000, rows)
    frame[RAW_TARGET] = (pay_0 + rng.normal(0, 1.5, rows) > 1).astype(int)
    return frame


def write_raw_csv(path: Path, raw: pd.DataFrame) -> Path:
    placeholder = ";".join(["", *[f"X{i}" for i in range(1, 24)], "Y"])
    path.write_text(placeholder + "\n" + raw.to_csv(sep=";", index=False), encoding="utf-8")
    return path
