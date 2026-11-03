import hashlib

import pytest
from conftest import RAW_TARGET, make_raw

from credit_monitoring.data.prepare import prepare_dataset, split_dataset
from credit_monitoring.data.simulate import (
    SimulationError,
    apply_scenario,
    prepare_production_batches,
)


@pytest.fixture
def m1_frames(config):
    raw = make_raw(config, rows=600).rename(columns={RAW_TARGET: "default_payment_next_month"})
    prepared, _ = prepare_dataset(raw, config)
    splits = split_dataset(prepared, config)
    return splits["train"], splits["validation"]


def test_production_copies_are_target_free_disjoint_and_reproducible(config, m1_frames):
    reference, validation = m1_frames
    source = validation.copy(deep=True)
    source_hash = hashlib.sha256(b"validated-input").hexdigest()

    original, modified = prepare_production_batches(
        validation,
        reference,
        config,
        validation_sha256=source_hash,
        expected_validation_sha256=source_hash,
    )
    again, modified_again = prepare_production_batches(
        validation,
        reference,
        config,
        validation_sha256=source_hash,
        expected_validation_sha256=source_hash,
    )

    assert "default_payment_next_month" not in original
    assert "default_payment_next_month" not in modified
    assert original.equals(again)
    assert modified.equals(modified_again)
    assert set(original.ID).isdisjoint(set(reference.ID))
    assert original.ID.is_unique and modified.ID.is_unique
    assert validation.equals(source)
    assert len(original) == len(modified) == len(validation)
    changed = [column for column in original if not original[column].equals(modified[column])]
    assert changed == ["LIMIT_BAL", "PAY_AMT1"]
    assert (modified["LIMIT_BAL"] > 0).all()
    assert original["PAY_AMT1"].eq(0).equals(modified["PAY_AMT1"].eq(0))


def test_production_generation_rejects_a_mismatched_validation_hash(config, m1_frames):
    reference, validation = m1_frames
    with pytest.raises(SimulationError, match="hash differs"):
        prepare_production_batches(
            validation,
            reference,
            config,
            validation_sha256="0" * 64,
            expected_validation_sha256="1" * 64,
        )


def test_production_generation_rejects_shared_ids(config, m1_frames):
    reference, validation = m1_frames
    validation.loc[validation.index[0], "ID"] = reference.iloc[0]["ID"]
    with pytest.raises(SimulationError, match="share"):
        prepare_production_batches(
            validation,
            reference,
            config,
            validation_sha256="a" * 64,
            expected_validation_sha256="a" * 64,
        )


def test_scenario_does_not_mutate_original_and_rejects_unsupported_rounding(config, m1_frames):
    _, validation = m1_frames
    original = validation.drop(columns=["default_payment_next_month"])
    before = original.copy(deep=True)
    apply_scenario(original, config)
    assert original.equals(before)

    config["drift"]["scenario"]["rounding"] = "half_up"
    with pytest.raises(SimulationError, match="Unsupported rounding"):
        apply_scenario(original, config)
