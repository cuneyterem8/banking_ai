import pandas as pd
import pytest

from app.use_cases.fraud_detection.data_generation import (
    ML_TRAIN_COUNT,
    ML_VAL_COUNT,
    TEST_COUNT,
    build_transactions,
    split_train_val_test,
)
from app.use_cases.fraud_detection.data_leakage import (
    DataLeakageError,
    assert_enrichment_ignores_label,
    assert_fit_frame_safe,
    assert_splits_disjoint,
    audit_training_inputs,
)
from app.use_cases.fraud_detection.feature_engineering import LABEL_COLUMN, prepare_ml_frame
from app.use_cases.fraud_detection.raw_data import (
    load_test_transactions,
    load_train_transactions,
    load_val_transactions,
)
def _rows():
    all_rows = build_transactions()
    return split_train_val_test(all_rows)


def test_splits_are_disjoint() -> None:
    train, val, test = _rows()
    assert_splits_disjoint(train, val, test)
    assert len(train) == ML_TRAIN_COUNT
    assert len(val) == ML_VAL_COUNT
    assert len(test) == TEST_COUNT


def test_enrichment_does_not_use_label() -> None:
    assert_enrichment_ignores_label()


def test_fit_frame_excludes_forbidden_and_ids() -> None:
    train, val, test = _rows()
    audit = audit_training_inputs(train, val, test)
    assert audit["status"] == "ok"
    assert "composite_risk_score" in audit["forbidden_columns_absent"]
    frame = prepare_ml_frame(train)
    assert_fit_frame_safe(frame)
    assert LABEL_COLUMN in frame.columns


def test_persisted_xlsx_splits_are_disjoint() -> None:
    train = [r.model_dump() for r in load_train_transactions()]
    val = [r.model_dump() for r in load_val_transactions()]
    test = [r.model_dump() for r in load_test_transactions()]
    assert_splits_disjoint(train, val, test)


def test_audit_rejects_overlapping_ids() -> None:
    train, val, _ = _rows()
    poisoned_val = [{**val[0], "transaction_id": train[0]["transaction_id"]}]
    with pytest.raises(DataLeakageError, match="Train/val overlap"):
        audit_training_inputs(train, poisoned_val, [])


def test_prepare_ml_frame_has_no_label_proxy_columns() -> None:
    train, _, _ = _rows()
    frame = prepare_ml_frame(train)
    assert "composite_risk_score" not in frame.columns
    assert "risk_flag_count" not in frame.columns
    assert "transaction_id" not in frame.columns
