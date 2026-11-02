import yaml

from credit_monitoring.paths import PROJECT_ROOT

EDA_SUMMARY = "reports/eda/eda_summary.json"
EXPLORATION_SUMMARY = "reports/explore/train_exploration.json"
RAW_CSV = "data/raw/default_of_credit_card_clients.csv"


def _stages() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "dvc.yaml").read_text(encoding="utf-8"))["stages"]


def _out_paths(stage: dict) -> list[str]:
    return [next(iter(out)) if isinstance(out, dict) else out for out in stage.get("outs", [])]


def test_pipeline_contains_m1_then_phase2_stages_in_dependency_order():
    assert list(_stages()) == [
        "acquire",
        "eda",
        "prepare",
        "explore",
        "tune",
        "train",
        "evaluate",
        "simulate_production",
        "score_production",
        "detect_drift",
    ]


def test_the_tuning_stage_reads_only_the_training_split():
    """The campaign of plan 1.6 must never see the validation or the test split."""
    stages = _stages()
    assert "data/processed/train.csv" in stages["tune"]["deps"]
    assert "data/processed/validation.csv" not in stages["tune"]["deps"]
    assert "data/processed/test.csv" not in stages["tune"]["deps"]
    assert "data/processed/test.csv" not in stages["tune"].get("outs", [])


def test_the_tuning_stage_does_not_own_the_published_model():
    """There is a single owner for the published artifact."""
    stages = _stages()
    assert "models/credit_model.joblib" not in _out_paths(stages["tune"])
    assert "models/credit_model.joblib" in _out_paths(stages["train"])


def test_the_selection_stage_consumes_the_frozen_finalists():
    stages = _stages()
    deps = stages["train"]["deps"]
    assert "reports/optimization/opt-20261026-01/tuning" in deps
    assert "models/optimization/opt-20261026-01/finalists" in deps
    assert "configs/optimization.yaml" in deps


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


def test_train_stage_never_depends_on_the_test_split():
    """The selection stage must not read the test partition."""
    stages = _stages()
    assert "data/processed/test.csv" not in stages["train"]["deps"]
    assert "data/processed/test.csv" not in stages["train"].get("outs", [])


def test_evaluate_is_a_separate_stage_that_owns_the_test_split():
    stages = _stages()
    assert "data/processed/test.csv" in stages["evaluate"]["deps"]
    assert "models/credit_model.joblib" in stages["evaluate"]["deps"]
    assert "data/processed/test.csv" not in stages["train"]["deps"]
    # The frozen artifact is produced by the selection stage and consumed by the
    # evaluation stage: it is an output of one stage and a dependency of the other.
    assert "models/credit_model.joblib" in _out_paths(stages["train"])
    assert "models/credit_model.joblib" not in _out_paths(stages["evaluate"])


def test_phase2_simulation_uses_validation_and_reference_not_test():
    stages = _stages()
    simulation = stages["simulate_production"]
    assert "data/processed/validation.csv" in simulation["deps"]
    assert "data/reference/reference.csv" in simulation["deps"]
    assert "data/processed/test.csv" not in simulation["deps"]
    assert "models/credit_model_metadata.json" in simulation["deps"]
    assert set(_out_paths(simulation)) == {
        "data/production/v1.0.2/original.csv",
        "data/production/v1.0.2/modified.csv",
        "data/production/v1.0.2/manifest.json",
    }


def test_phase2_scoring_uses_the_frozen_model_and_contract():
    stages = _stages()
    scoring = stages["score_production"]
    assert "models/credit_model.joblib" in scoring["deps"]
    assert "models/credit_model_metadata.json" in scoring["deps"]
    assert "src/credit_monitoring/contracts" in scoring["deps"]
    assert "src/credit_monitoring/data/simulate.py" in scoring["deps"]
    assert "src/credit_monitoring/data/loading.py" in scoring["deps"]
    assert "data/processed/test.csv" not in scoring["deps"]
    assert "data/production/v1.0.2/predictions/original.csv" in _out_paths(scoring)
    assert "data/production/v1.0.2/predictions/modified.csv" in _out_paths(scoring)


def test_phase2_drift_consumes_both_batches_predictions_and_reference():
    stages = _stages()
    detection = stages["detect_drift"]
    assert "data/reference/reference.csv" in detection["deps"]
    assert "data/production/v1.0.2/original.csv" in detection["deps"]
    assert "data/production/v1.0.2/modified.csv" in detection["deps"]
    assert "reports/drift/prediction_summary-v1.0.2.json" in detection["deps"]
    assert "reports/metrics.json" in detection["deps"]
    assert "reports/test_metrics.json" in detection["deps"]
    assert "reports/eda/eda_summary.json" in detection["deps"]
    assert "data/processed/preparation_report.json" in detection["deps"]
    assert "reports/optimization/opt-20261026-01/tuning/manifest.json" in detection["deps"]
    assert "reports/optimization/opt-20261026-01/selection/comparison.json" in detection["deps"]
    assert "configs/optimization.yaml" in detection["deps"]
    assert "src/credit_monitoring/models/train.py" in detection["deps"]
    assert "src/credit_monitoring/models/tune.py" in detection["deps"]
    assert "src/credit_monitoring/monitoring/report_context.py" in detection["deps"]
    assert "src/credit_monitoring/monitoring/drift_report_template.html" in detection["deps"]
    assert "reports/drift/results-v1.0.2.json" in _out_paths(detection)
    assert "reports/drift/phase-2-drift-v1.0.2-ptbr-v6.html" in _out_paths(detection)


def test_no_file_is_tracked_as_the_output_of_two_stages():
    stages = _stages()
    owners: dict[str, str] = {}
    for name, stage in stages.items():
        for path in _out_paths(stage):
            assert path not in owners, f"{path} is an output of {owners[path]} and {name}"
            owners[path] = name


def test_source_workbook_is_an_object_of_dvc_and_not_a_git_file():
    """The 5,5 MB binary must live in DVC, not in the Git history (team decision)."""
    pointer = PROJECT_ROOT / "data" / "default of credit card clients.xls.dvc"
    assert pointer.is_file()
    content = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    assert content["outs"][0]["md5"] == "c0a9cb828ded9c446574ede877bf1f6e"
    assert content["outs"][0]["size"] == 5539328
