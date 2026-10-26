import json

import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw, write_raw_csv

from credit_monitoring.config import canonical_columns
from credit_monitoring.data.loading import file_sha256, load_raw
from credit_monitoring.data.prepare import (
    assert_eda_matches_raw,
    prepare_dataset,
    run_preparation,
    split_dataset,
)


def _canonical(config, raw=None):
    raw = make_raw(config) if raw is None else raw
    return prepare_dataset(raw.rename(columns={RAW_TARGET: "default_payment_next_month"}), config)


def test_load_raw_skips_leading_x_line_and_renames_target(tmp_path, config):
    raw = make_raw(config, rows=50)
    loaded = load_raw(write_raw_csv(tmp_path / "raw.csv", raw), config)
    assert set(loaded.columns) == set(canonical_columns(config))
    assert len(loaded) == 50


def test_prepare_dataset_keeps_valid_rows_and_canonical_columns(config):
    prepared, report = _canonical(config)
    assert list(prepared.columns) == canonical_columns(config)
    assert report.removed_rows == 0
    assert report.output_rows == report.input_rows == 600


def test_prepare_dataset_removes_and_counts_invalid_rows(config):
    raw = make_raw(config).rename(columns={RAW_TARGET: "default_payment_next_month"})
    raw.loc[0, "LIMIT_BAL"] = None
    raw.loc[1, "ID"] = raw.loc[2, "ID"]
    raw.loc[3, "default_payment_next_month"] = 2
    raw.loc[4, "LIMIT_BAL"] = 0
    raw.loc[5, "AGE"] = 5
    raw.loc[6, "AGE"] = 101

    prepared, report = prepare_dataset(raw, config)

    assert report.null_or_non_numeric_rows == 1
    assert report.duplicated_id_rows == 1
    assert report.invalid_target_rows == 1
    assert report.non_positive_limit_rows == 1
    assert report.age_out_of_range_rows == 2
    assert report.removed_rows == 6
    assert len(prepared) == 594
    assert prepared["ID"].is_unique


def test_prepare_dataset_keeps_undocumented_codes(config):
    raw = make_raw(config).rename(columns={RAW_TARGET: "default_payment_next_month"})
    raw.loc[0, "EDUCATION"] = 0
    raw.loc[1, "MARRIAGE"] = 0
    prepared, _ = prepare_dataset(raw, config)
    assert (prepared["EDUCATION"] == 0).sum() == 1
    assert (prepared["MARRIAGE"] == 0).sum() == 1


def test_split_is_stratified_70_15_15_without_id_leakage(config):
    prepared, _ = _canonical(config)
    splits = split_dataset(prepared, config)
    target = config["dataset"]["canonical_target"]

    assert {name: len(frame) for name, frame in splits.items()} == {
        "train": 420,
        "validation": 90,
        "test": 90,
    }
    overall = prepared[target].mean()
    for frame in splits.values():
        assert frame[target].mean() == pytest.approx(overall, abs=0.02)
    all_ids = pd.concat([frame["ID"] for frame in splits.values()])
    assert all_ids.is_unique
    assert len(all_ids) == len(prepared)


def test_split_is_reproducible_and_seed_sensitive(config):
    prepared, _ = _canonical(config)
    first = split_dataset(prepared, config)
    second = split_dataset(prepared, config)
    other = split_dataset(prepared, config, random_state=7)
    pd.testing.assert_frame_equal(first["train"], second["train"])
    assert not first["train"]["ID"].equals(other["train"]["ID"])


@pytest.mark.parametrize(
    "split",
    [
        {"train": 0.7, "validation": 0.2, "test": 0.2},
        {"train": 1.0, "validation": 0.0, "test": 0.0},
    ],
)
def test_split_rejects_invalid_ratios(config, split):
    prepared, _ = _canonical(config)
    config["dataset"]["split"] = split
    with pytest.raises(ValueError):
        split_dataset(prepared, config)


def test_preparation_requires_matching_eda_summary(tmp_path, config):
    raw_csv = write_raw_csv(tmp_path / "raw.csv", make_raw(config))
    sha = file_sha256(raw_csv)

    with pytest.raises(FileNotFoundError):
        assert_eda_matches_raw(tmp_path / "missing.json", sha)

    summary = tmp_path / "eda_summary.json"
    summary.write_text(json.dumps({"raw_sha256": "outro"}), encoding="utf-8")
    with pytest.raises(ValueError):
        assert_eda_matches_raw(summary, sha)


def test_run_preparation_writes_splits_reference_and_report(tmp_path, config):
    raw_csv = write_raw_csv(tmp_path / "raw.csv", make_raw(config))
    eda_summary = tmp_path / "eda_summary.json"
    eda_summary.write_text(json.dumps({"raw_sha256": file_sha256(raw_csv)}), encoding="utf-8")

    summary = run_preparation(
        raw_csv,
        config,
        eda_summary_path=eda_summary,
        processed_dir=tmp_path / "processed",
        reference_dir=tmp_path / "reference",
    )

    for name in ("train", "validation", "test"):
        assert (tmp_path / "processed" / f"{name}.csv").is_file()
    assert (tmp_path / "processed" / "preparation_report.json").is_file()
    train = pd.read_csv(tmp_path / "processed" / "train.csv")
    reference = pd.read_csv(tmp_path / "reference" / "reference.csv")
    pd.testing.assert_frame_equal(train, reference)
    assert summary["splits"]["train"]["rows"] == 420


def test_removed_rows_counts_unique_rows_not_the_sum_of_reasons(config):
    raw = make_raw(config).rename(columns={RAW_TARGET: "default_payment_next_month"})
    # The same row violates two rules at once: duplicated ID and invalid target.
    raw.loc[2, "ID"] = raw.loc[1, "ID"]
    raw.loc[2, "default_payment_next_month"] = 2

    _, report = prepare_dataset(raw, config)

    assert report.duplicated_id_rows == 1
    assert report.invalid_target_rows == 1
    assert report.removed_rows == 1
    assert report.rows_matching_multiple_reasons == 1
    assert report.input_rows == report.output_rows + report.removed_rows


def test_preparation_report_records_split_and_reference_evidence(tmp_path, config):
    raw_csv = write_raw_csv(tmp_path / "raw.csv", make_raw(config))
    eda_summary = tmp_path / "eda_summary.json"
    eda_summary.write_text(json.dumps({"raw_sha256": file_sha256(raw_csv)}), encoding="utf-8")

    summary = run_preparation(
        raw_csv,
        config,
        eda_summary_path=eda_summary,
        processed_dir=tmp_path / "processed",
        reference_dir=tmp_path / "reference",
    )

    assert summary["cleaning"]["removed_rows"] == 0
    assert "Nenhuma linha foi removida" in summary["cleaning_note"]
    assert summary["useful_rows"] == {
        "minimum_required": 5000,
        "after_cleaning": 600,
        "meets_minimum": False,
    }
    assert summary["id_audit"]["id_intersections"] == {}
    assert summary["id_audit"]["coverage_complete"] is True
    assert summary["id_audit"]["ids_unique_within_split"] == {
        "train": True,
        "validation": True,
        "test": True,
    }
    assert summary["reference"]["identical_to_train"] is True
    assert summary["reference"]["sha256"] == summary["reference"]["train_sha256"]
