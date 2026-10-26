"""Cleaning and stratified splitting of the credit default dataset."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

from credit_monitoring.config import canonical_columns, load_config
from credit_monitoring.data.loading import default_raw_path, file_sha256, load_raw
from credit_monitoring.eda import DEFAULT_SUMMARY_PATH
from credit_monitoring.paths import PROCESSED_DATA_DIR, REFERENCE_DATA_DIR

REPORT_FILE = "preparation_report.json"
SPLIT_NAMES = ("train", "validation", "test")


@dataclass(frozen=True)
class PreparationReport:
    input_rows: int
    null_or_non_numeric_rows: int
    duplicated_id_rows: int
    invalid_target_rows: int
    non_positive_limit_rows: int
    age_out_of_range_rows: int
    removed_rows: int
    rows_matching_multiple_reasons: int
    output_rows: int


def prepare_dataset(
    raw: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, PreparationReport]:
    """Return the canonical frame with only structurally invalid rows removed."""
    dataset = config["dataset"]
    contract = config["contract"]
    columns = canonical_columns(config)
    id_column = dataset["id_column"]
    target = dataset["canonical_target"]

    numeric = raw[columns].apply(pd.to_numeric, errors="coerce")
    null_mask = numeric.isna().any(axis=1)
    duplicated_id_mask = numeric[id_column].duplicated(keep="first") & ~null_mask
    invalid_target_mask = ~null_mask & ~numeric[target].isin([0, 1])
    non_positive_limit_mask = ~null_mask & (numeric["LIMIT_BAL"] <= 0)
    age_mask = ~null_mask & ~numeric["AGE"].between(contract["age_min"], contract["age_max"])

    masks = [
        null_mask,
        duplicated_id_mask,
        invalid_target_mask,
        non_positive_limit_mask,
        age_mask,
    ]
    # ``removed_rows`` counts unique removed rows (the union), never the sum of reasons.
    drop = null_mask.copy()
    for mask in masks:
        drop = drop | mask
    reasons_hit = sum(mask.astype(int) for mask in masks)
    prepared = numeric.loc[~drop].astype(int).reset_index(drop=True)
    report = PreparationReport(
        input_rows=len(raw),
        null_or_non_numeric_rows=int(null_mask.sum()),
        duplicated_id_rows=int(duplicated_id_mask.sum()),
        invalid_target_rows=int(invalid_target_mask.sum()),
        non_positive_limit_rows=int(non_positive_limit_mask.sum()),
        age_out_of_range_rows=int(age_mask.sum()),
        removed_rows=int(drop.sum()),
        rows_matching_multiple_reasons=int((reasons_hit > 1).sum()),
        output_rows=len(prepared),
    )
    return prepared, report


def _split_ratios(config: dict[str, Any]) -> dict[str, float]:
    ratios = {name: float(config["dataset"]["split"][name]) for name in SPLIT_NAMES}
    if any(not 0 < ratio < 1 for ratio in ratios.values()):
        raise ValueError(f"Split ratios must be in (0, 1): {ratios}")
    if abs(sum(ratios.values()) - 1) > 1e-9:
        raise ValueError(f"Split ratios must sum to 1: {ratios}")
    return ratios


def split_dataset(
    data: pd.DataFrame, config: dict[str, Any], *, random_state: int | None = None
) -> dict[str, pd.DataFrame]:
    """Stratified train/validation/test split; raises if any ID is shared between splits."""
    ratios = _split_ratios(config)
    seed = config["project"]["random_seed"] if random_state is None else random_state
    target = config["dataset"]["canonical_target"]
    id_column = config["dataset"]["id_column"]

    holdout = ratios["validation"] + ratios["test"]
    train, rest = train_test_split(
        data, test_size=holdout, stratify=data[target], random_state=seed
    )
    validation, test = train_test_split(
        rest, test_size=ratios["test"] / holdout, stratify=rest[target], random_state=seed
    )
    splits = {
        "train": train.reset_index(drop=True),
        "validation": validation.reset_index(drop=True),
        "test": test.reset_index(drop=True),
    }
    ids = [set(frame[id_column]) for frame in splits.values()]
    if sum(len(item) for item in ids) != len(set().union(*ids)):
        raise AssertionError("ID leakage between splits")
    return splits


def assert_eda_matches_raw(summary_path: Path, raw_sha256: str) -> None:
    """The EDA must have been run on the exact raw file being prepared."""
    if not summary_path.is_file():
        raise FileNotFoundError(f"EDA summary not found: {summary_path}. Run the EDA first.")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("raw_sha256") != raw_sha256:
        raise ValueError("EDA summary was generated from a different raw file. Re-run the EDA.")


MINIMUM_USEFUL_ROWS = 5000
REFERENCE_FILE = "reference.csv"


def audit_split_ids(splits: dict[str, pd.DataFrame], id_column: str) -> dict[str, Any]:
    """Evidence that IDs are unique inside each split and disjoint across splits."""
    ids = {name: set(frame[id_column]) for name, frame in splits.items()}
    intersections = {}
    names = list(ids)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            shared = ids[left] & ids[right]
            if shared:
                intersections[f"{left}&{right}"] = len(shared)
    total = sum(len(frame) for frame in splits.values())
    unique = len(set().union(*ids.values()))
    return {
        "ids_unique_within_split": {
            name: bool(frame[id_column].is_unique) for name, frame in splits.items()
        },
        "id_intersections": intersections,
        "sum_of_split_rows": total,
        "unique_ids_across_splits": unique,
        "coverage_complete": total == unique,
    }


def run_preparation(
    raw_csv: str | Path,
    config: dict[str, Any],
    *,
    eda_summary_path: str | Path = DEFAULT_SUMMARY_PATH,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    reference_dir: str | Path = REFERENCE_DATA_DIR,
) -> dict[str, Any]:
    raw_csv = Path(raw_csv)
    raw_sha256 = file_sha256(raw_csv)
    assert_eda_matches_raw(Path(eda_summary_path), raw_sha256)

    target = config["dataset"]["canonical_target"]
    id_column = config["dataset"]["id_column"]
    prepared, report = prepare_dataset(load_raw(raw_csv, config), config)
    splits = split_dataset(prepared, config)

    processed_dir = Path(processed_dir)
    reference_dir = Path(reference_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in splits.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False)
    # Reference for drift monitoring is the untouched training split.
    splits["train"].to_csv(reference_dir / REFERENCE_FILE, index=False)

    train_sha256 = file_sha256(processed_dir / "train.csv")
    reference_sha256 = file_sha256(reference_dir / REFERENCE_FILE)
    summary = {
        "raw_sha256": raw_sha256,
        "random_seed": config["project"]["random_seed"],
        "cleaning": asdict(report),
        "cleaning_note": (
            "Nenhuma linha foi removida no dado real: as cinco regras de limpeza nao "
            "dispararam. O caminho de remocao continua coberto por fixture controlada "
            "em tests/test_data_preparation.py; ausencia de remocao nao e ausencia de "
            "verificacao."
            if report.removed_rows == 0
            else (
                f"{report.removed_rows} linhas unicas removidas; ver contagens por motivo "
                "e sobreposicao em 'cleaning'."
            )
        ),
        "useful_rows": {
            "minimum_required": MINIMUM_USEFUL_ROWS,
            "after_cleaning": report.output_rows,
            "meets_minimum": report.output_rows >= MINIMUM_USEFUL_ROWS,
        },
        "splits": {
            name: {
                "rows": len(frame),
                "target_rate": round(float(frame[target].mean()), 4),
            }
            for name, frame in splits.items()
        },
        "id_audit": audit_split_ids(splits, id_column),
        "reference": {
            "file": REFERENCE_FILE,
            "sha256": reference_sha256,
            "train_sha256": train_sha256,
            "identical_to_train": reference_sha256 == train_sha256,
        },
    }
    (processed_dir / REPORT_FILE).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Limpa e divide o dataset (70/15/15).")
    parser.add_argument("--config", default=None)
    parser.add_argument("--raw-csv", default=None)
    parser.add_argument("--eda-summary", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--reference-dir", default=str(REFERENCE_DATA_DIR))
    args = parser.parse_args(argv)

    config = load_config(args.config)
    summary = run_preparation(
        args.raw_csv or default_raw_path(config),
        config,
        eda_summary_path=args.eda_summary,
        processed_dir=args.processed_dir,
        reference_dir=args.reference_dir,
    )
    rows = {name: item["rows"] for name, item in summary["splits"].items()}
    print(f"Preparacao concluida: {rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
