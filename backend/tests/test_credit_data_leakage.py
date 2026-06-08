import pytest

from app.use_cases.credit_risk.data_generation import ML_TRAIN_COUNT, ML_VAL_COUNT, TEST_COUNT, build_applications, split_train_val_test
from app.use_cases.credit_risk.data_leakage import (
    DataLeakageError,
    assert_enrichment_ignores_label,
    assert_splits_disjoint,
    audit_training_inputs,
)
from app.use_cases.credit_risk.feature_engineering import prepare_ml_frame


def _rows():
    return split_train_val_test(build_applications())


def test_credit_splits_are_disjoint() -> None:
    train, val, test = _rows()
    assert_splits_disjoint(train, val, test)
    assert len(train) == ML_TRAIN_COUNT
    assert len(val) == ML_VAL_COUNT
    assert len(test) == TEST_COUNT


def test_credit_enrichment_does_not_use_targets() -> None:
    assert_enrichment_ignores_label()


def test_credit_audit_rejects_overlap() -> None:
    train, val, _ = _rows()
    poisoned_val = [{**val[0], "application_id": train[0]["application_id"]}]
    with pytest.raises(DataLeakageError, match="Train/val overlap"):
        audit_training_inputs(train, poisoned_val, [])


def test_credit_fit_frame_has_no_target_proxy_columns() -> None:
    train, val, test = _rows()
    audit = audit_training_inputs(train, val, test)
    assert audit["status"] == "ok"
    frame = prepare_ml_frame(train)
    assert "target_loss_given_default" not in frame.columns
    assert "application_id" not in frame.columns
