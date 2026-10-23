import json

from conftest import make_raw, write_raw_csv

from credit_monitoring.data.loading import file_sha256, load_raw
from credit_monitoring.eda import PLOTS, build_summary, run_eda


def test_build_summary_reports_quality_and_undocumented_codes(tmp_path, config):
    raw = make_raw(config)
    raw.loc[0, "EDUCATION"] = 5
    raw.loc[1, "MARRIAGE"] = 0
    raw.loc[2, "BILL_AMT1"] = -50
    raw_csv = write_raw_csv(tmp_path / "raw.csv", raw)

    summary = build_summary(
        load_raw(raw_csv, config), config, raw_sha256=file_sha256(raw_csv), raw_file="raw.csv"
    )

    assert summary["rows"] == 600
    assert summary["null_values"] == 0
    assert summary["duplicated_ids"] == 0
    assert summary["undocumented_codes"]["EDUCATION"] == {"5": 1}
    assert summary["undocumented_codes"]["MARRIAGE"] == {"0": 1}
    assert summary["undocumented_codes"]["PAY"]
    assert summary["negative_bill_amt_values"] >= 1
    assert 0 < summary["target_rate"] < 1
    assert summary["raw_sha256"] == file_sha256(raw_csv)


def test_run_eda_writes_summary_and_all_figures(tmp_path, config):
    raw_csv = write_raw_csv(tmp_path / "raw.csv", make_raw(config))
    figures_dir = tmp_path / "figures"
    summary_path = tmp_path / "reports" / "eda_summary.json"

    summary = run_eda(raw_csv, config, figures_dir=figures_dir, summary_path=summary_path)

    assert len(list(figures_dir.glob("*.png"))) == len(PLOTS)
    assert json.loads(summary_path.read_text(encoding="utf-8")) == summary


def test_run_eda_summary_is_deterministic(tmp_path, config):
    raw_csv = write_raw_csv(tmp_path / "raw.csv", make_raw(config))
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path in paths:
        run_eda(raw_csv, config, figures_dir=tmp_path / "figures", summary_path=path)
    assert paths[0].read_bytes() == paths[1].read_bytes()
