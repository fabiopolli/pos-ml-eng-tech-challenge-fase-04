import yaml

from credit_monitoring.paths import PROJECT_ROOT

EDA_SUMMARY = "reports/eda/eda_summary.json"
EXPLORATION_SUMMARY = "reports/explore/train_exploration.json"
RAW_CSV = "data/raw/default_of_credit_card_clients.csv"


def _stages() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "dvc.yaml").read_text(encoding="utf-8"))["stages"]


def _out_paths(stage: dict) -> list[str]:
    return [next(iter(out)) if isinstance(out, dict) else out for out in stage.get("outs", [])]


def test_pipeline_stage_order_is_acquire_eda_prepare_explore_train():
    assert list(_stages()) == ["acquire", "eda", "prepare", "explore", "train"]


def test_acquire_rebuilds_the_raw_csv_from_the_source_workbook():
    stages = _stages()
    assert "data/default of credit card clients.xls" in stages["acquire"]["deps"]
    assert RAW_CSV in _out_paths(stages["acquire"])


def test_prepare_depends_on_eda_output():
    stages = _stages()
    assert EDA_SUMMARY in _out_paths(stages["eda"])
    assert EDA_SUMMARY in stages["prepare"]["deps"]


def test_explore_depends_only_on_the_training_split():
    stages = _stages()
    assert "data/processed/train.csv" in stages["explore"]["deps"]
    assert "data/processed/validation.csv" not in stages["explore"]["deps"]
    assert "data/processed/test.csv" not in stages["explore"]["deps"]
    assert EXPLORATION_SUMMARY in _out_paths(stages["explore"])


def test_train_depends_on_prepare_outputs():
    stages = _stages()
    prepared = set(_out_paths(stages["prepare"]))
    assert {"data/processed/train.csv", "data/processed/validation.csv"} <= prepared
    assert prepared & set(stages["train"]["deps"]) >= {
        "data/processed/train.csv",
        "data/processed/validation.csv",
    }
