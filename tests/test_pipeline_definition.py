import yaml

from credit_monitoring.paths import PROJECT_ROOT

EDA_SUMMARY = "reports/eda/eda_summary.json"


def _stages() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "dvc.yaml").read_text(encoding="utf-8"))["stages"]


def _out_paths(stage: dict) -> list[str]:
    return [next(iter(out)) if isinstance(out, dict) else out for out in stage.get("outs", [])]


def test_pipeline_stage_order_is_eda_prepare_train():
    assert list(_stages()) == ["eda", "prepare", "train"]


def test_prepare_depends_on_eda_output():
    stages = _stages()
    assert EDA_SUMMARY in _out_paths(stages["eda"])
    assert EDA_SUMMARY in stages["prepare"]["deps"]


def test_train_depends_on_prepare_outputs():
    stages = _stages()
    prepared = set(_out_paths(stages["prepare"]))
    assert {"data/processed/train.csv", "data/processed/validation.csv"} <= prepared
    assert prepared & set(stages["train"]["deps"]) >= {
        "data/processed/train.csv",
        "data/processed/validation.csv",
        "data/processed/test.csv",
    }
