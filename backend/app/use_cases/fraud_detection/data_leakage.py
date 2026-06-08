"""
Data-leakage checks for Fraud Detection training and evaluation.

Training uses the train-fit slice for model weights and a stratified train holdout for
AutoGluon early stopping. Validation is for threshold tuning and metrics only; test is
never read during fit or threshold calibration.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.use_cases.fraud_detection.feature_engineering import (
    DROP_FOR_ML,
    LABEL_COLUMN,
    enrich_transaction_row,
    prepare_ml_frame,
)

FORBIDDEN_FEATURE_COLUMNS = frozenset(
    {
        LABEL_COLUMN,
        "sample_weight",
        # Removed from pipeline; fail fast if they reappear in stored data.
        "composite_risk_score",
        "risk_flag_count",
        # prior_risk_probability is allowed: derived from raw fields only, not from label_is_fraud.
    }
)


class DataLeakageError(ValueError):
    """Raised when the fraud pipeline would leak labels or holdout rows into training."""


def transaction_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["transaction_id"]) for row in rows}


def assert_splits_disjoint(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
) -> None:
    train_ids = transaction_ids(train_rows)
    val_ids = transaction_ids(val_rows)
    test_ids = transaction_ids(test_rows)

    if train_ids & val_ids:
        raise DataLeakageError(f"Train/val overlap: {len(train_ids & val_ids)} duplicate transaction_id values.")
    if train_ids & test_ids:
        raise DataLeakageError(f"Train/test overlap: {len(train_ids & test_ids)} duplicate transaction_id values.")
    if val_ids & test_ids:
        raise DataLeakageError(f"Val/test overlap: {len(val_ids & test_ids)} duplicate transaction_id values.")


def assert_enrichment_ignores_label() -> None:
    """Feature engineering must not read label_is_fraud."""
    row = {
        "transaction_id": "TXN-LEAK-001",
        "customer_id": "CUST-1",
        "account_age_days": 100,
        "amount": 50.0,
        "currency": "USD",
        "merchant_id": "MRC-1",
        "merchant_category": "grocery",
        "merchant_risk_score": 0.1,
        "channel": "card_present",
        "transaction_type": "purchase",
        "card_type": "debit",
        "country": "US",
        "is_international": 0,
        "device_trust_score": 0.9,
        "ip_risk_score": 0.1,
        "auth_method": "pin",
        "device_os": "ios",
        "session_duration_minutes": 10,
        "failed_login_count_24h": 0,
        "velocity_24h_count": 2,
        "days_since_last_transaction": 1,
        "prior_chargebacks": 0,
        "hour_of_day": 12,
        "is_new_payee": 0,
        "distance_from_home_km": 5.0,
        "avg_30d_amount": 45.0,
        "account_balance_before": 500.0,
        "label_is_fraud": 1,
    }
    without_label = {k: v for k, v in row.items() if k != LABEL_COLUMN}
    with_label = dict(row)
    with_label[LABEL_COLUMN] = 0

    enriched_a = enrich_transaction_row(without_label)
    enriched_b = enrich_transaction_row(with_label)
    keys = [k for k in enriched_a if k not in row and k not in FORBIDDEN_FEATURE_COLUMNS]
    for key in keys:
        if enriched_a.get(key) != enriched_b.get(key):
            raise DataLeakageError(f"Feature '{key}' changes when label_is_fraud changes (label leakage).")


def assert_fit_frame_safe(train_frame: pd.DataFrame) -> None:
    feature_columns = [c for c in train_frame.columns if c != LABEL_COLUMN]
    leaked = set(feature_columns) & FORBIDDEN_FEATURE_COLUMNS
    if leaked:
        raise DataLeakageError(f"Forbidden columns in train features: {sorted(leaked)}")

    for column in DROP_FOR_ML:
        if column in feature_columns:
            raise DataLeakageError(f"High-cardinality id '{column}' must be dropped before fit.")

    if LABEL_COLUMN not in train_frame.columns:
        raise DataLeakageError("Train frame must include label_is_fraud as the target column only.")


def assert_train_rows_only(train_rows: list[dict[str, Any]], fit_frame: pd.DataFrame) -> None:
    if len(fit_frame) != len(train_rows):
        raise DataLeakageError("Fit frame row count must match train split only (no val/test rows).")


def audit_training_inputs(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run all pre-train leakage checks; returns a summary for logs and tests."""
    assert_splits_disjoint(train_rows, val_rows, test_rows)
    assert_enrichment_ignores_label()

    train_frame = prepare_ml_frame(train_rows)
    assert_fit_frame_safe(train_frame)
    assert_train_rows_only(train_rows, train_frame)

    return {
        "status": "ok",
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "test_rows": len(test_rows),
        "train_features": [c for c in train_frame.columns if c != LABEL_COLUMN],
        "dropped_ids": list(DROP_FOR_ML),
        "forbidden_columns_absent": sorted(FORBIDDEN_FEATURE_COLUMNS - set(train_frame.columns)),
        "policy": {
            "fit_data": "train split (model weights)",
            "val_used_for": "threshold tuning + validation metrics (never in AutoGluon fit)",
            "train_holdout_used_for": "AutoGluon tuning_data + bagged holdout (stratified slice of train)",
            "test_used_for": "evaluate_test only after training",
            "anti_overfit": "refit_full=False, use_bag_holdout=True, test never in fit",
            "feature_engineering": "per-row, no label, no global test/val statistics",
        },
    }
