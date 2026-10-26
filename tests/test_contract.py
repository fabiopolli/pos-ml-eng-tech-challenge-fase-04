import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from conftest import RAW_TARGET, make_raw

from credit_monitoring.config import load_config
from credit_monitoring.contracts import (
    CONTRACT_VERSION,
    ContractViolation,
    validate_batch,
    validate_file,
)
from credit_monitoring.contracts.schema import expected_columns

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def valid_batch(config) -> pd.DataFrame:
    raw = make_raw(config, rows=200).rename(columns={RAW_TARGET: "default_payment_next_month"})
    return raw[expected_columns(config, labeled=True)].copy()


def test_valid_batch_is_accepted(valid_batch, config):
    validated = validate_batch(valid_batch, config)
    assert len(validated) == len(valid_batch)


def test_inference_batch_without_target_is_accepted(valid_batch, config):
    inference = valid_batch.drop(columns=["default_payment_next_month"])
    validated = validate_batch(inference, config, labeled=False)
    assert len(validated) == len(inference)


def test_duplicate_id_is_rejected(valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[1], "ID"] = invalid.loc[invalid.index[0], "ID"]
    with pytest.raises(ContractViolation) as error:
        validate_batch(invalid, config)
    assert "ID" in str(error.value)


def test_non_positive_limit_bal_is_rejected(valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[0], "LIMIT_BAL"] = 0
    with pytest.raises(ContractViolation):
        validate_batch(invalid, config)


def test_age_out_of_range_is_rejected(valid_batch, config):
    for age in (17, 101):
        invalid = valid_batch.copy()
        invalid.loc[invalid.index[0], "AGE"] = age
        with pytest.raises(ContractViolation):
            validate_batch(invalid, config)


def test_age_boundaries_are_accepted(valid_batch, config):
    boundary = valid_batch.copy()
    boundary.loc[boundary.index[0], "AGE"] = config["contract"]["age_min"]
    boundary.loc[boundary.index[1], "AGE"] = config["contract"]["age_max"]
    assert len(validate_batch(boundary, config)) == len(boundary)


def test_null_feature_is_rejected(valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[0], "PAY_AMT1"] = None
    with pytest.raises(ContractViolation):
        validate_batch(invalid, config)


def test_missing_column_is_rejected(valid_batch, config):
    invalid = valid_batch.drop(columns=["BILL_AMT3"])
    with pytest.raises(ContractViolation) as error:
        validate_batch(invalid, config)
    assert "BILL_AMT3" in str(error.value)


def test_incompatible_type_is_rejected(valid_batch, config):
    invalid = valid_batch.copy()
    invalid["PAY_AMT2"] = invalid["PAY_AMT2"].astype(object)
    invalid.loc[invalid.index[0], "PAY_AMT2"] = "not-a-number"
    with pytest.raises(ContractViolation):
        validate_batch(invalid, config)


def test_invalid_target_is_rejected(valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[0], "default_payment_next_month"] = 7
    with pytest.raises(ContractViolation):
        validate_batch(invalid, config)


def test_batch_is_counted_once_when_several_rules_fail(valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[0], "LIMIT_BAL"] = -1
    invalid.loc[invalid.index[1], "AGE"] = 5
    invalid.loc[invalid.index[2], "default_payment_next_month"] = 3
    with pytest.raises(ContractViolation) as error:
        validate_batch(invalid, config)
    assert error.value.rejected_rows == len(invalid)
    assert len(error.value.rules) >= 3


def test_diagnostic_reports_rule_column_and_count_without_client_records(valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[0], "LIMIT_BAL"] = 0
    with pytest.raises(ContractViolation) as error:
        validate_batch(invalid, config)
    payload = error.value.to_dict()
    assert payload["rejected_rows"] == len(invalid)
    assert payload["failed_rules"]
    for rule in payload["failed_rules"]:
        assert set(rule) <= {"rule", "column", "count", "check"}
    assert "not-a-number" not in json.dumps(payload)


def test_validate_file_rejects_unreadable_batch(tmp_path, valid_batch, config):
    path = tmp_path / "batch.csv"
    valid_batch.to_csv(path, index=False)
    assert len(validate_file(path, config)) == len(valid_batch)


def test_cli_accepts_valid_batch(tmp_path, valid_batch, config):
    path = tmp_path / "batch.csv"
    valid_batch.to_csv(path, index=False)
    result = subprocess.run(
        [sys.executable, "-m", "credit_monitoring.contracts.validate", "--input", str(path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "accepted"
    assert payload["contract_version"] == CONTRACT_VERSION


def test_cli_rejects_invalid_batch_with_non_zero_exit(tmp_path, valid_batch, config):
    invalid = valid_batch.copy()
    invalid.loc[invalid.index[0], "AGE"] = 5
    path = tmp_path / "batch.csv"
    invalid.to_csv(path, index=False)
    result = subprocess.run(
        [sys.executable, "-m", "credit_monitoring.contracts.validate", "--input", str(path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "rejected"
    assert payload["rejected_rows"] == len(invalid)


def test_cli_accepts_inference_batch_without_target(tmp_path, valid_batch, config):
    path = tmp_path / "batch.csv"
    valid_batch.drop(columns=["default_payment_next_month"]).to_csv(path, index=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "credit_monitoring.contracts.validate",
            "--input",
            str(path),
            "--inference",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0


def test_contract_rules_come_from_the_configuration_block(config):
    from credit_monitoring.contracts.schema import build_labeled_schema

    schema = build_labeled_schema(config)
    assert schema.name == f"credit_monitoring_labeled_v{CONTRACT_VERSION}"
    assert config["contract"]["age_min"] == 18
    assert config["contract"]["age_max"] == 100


def test_negative_bill_amounts_and_undocumented_codes_are_accepted(valid_batch, config):
    permissive = valid_batch.copy()
    permissive.loc[permissive.index[0], "BILL_AMT1"] = -50
    permissive.loc[permissive.index[1], "EDUCATION"] = 0
    permissive.loc[permissive.index[2], "MARRIAGE"] = 0
    permissive.loc[permissive.index[3], "PAY_0"] = -2
    assert len(validate_batch(permissive, config)) == len(permissive)


def test_governance_columns_are_required(valid_batch, config):
    invalid = valid_batch.drop(columns=["SEX"])
    with pytest.raises(ContractViolation):
        validate_batch(invalid, config)


def test_default_configuration_is_loaded_from_the_repository():
    config = load_config()
    assert config["project"]["random_seed"] == 42
