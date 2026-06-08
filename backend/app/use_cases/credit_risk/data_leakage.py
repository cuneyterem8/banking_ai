from __future__ import annotations

from typing import Any

import pandas as pd

from app.use_cases.credit_risk.feature_engineering import (
    DROP_FOR_ML,
    LABEL_COLUMN,
    LGD_COLUMN,
    enrich_application_row,
    prepare_ml_frame,
)

FORBIDDEN_FEATURE_COLUMNS = frozenset({LABEL_COLUMN, LGD_COLUMN, "sample_weight"})


class DataLeakageError(ValueError):
    """Raised when credit risk training would leak labels or holdout rows."""


def application_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["application_id"]) for row in rows}


def assert_splits_disjoint(train_rows: list[dict[str, Any]], val_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]]) -> None:
    train_ids = application_ids(train_rows)
    val_ids = application_ids(val_rows)
    test_ids = application_ids(test_rows)
    if train_ids & val_ids:
        raise DataLeakageError(f"Train/val overlap: {len(train_ids & val_ids)} duplicate application_id values.")
    if train_ids & test_ids:
        raise DataLeakageError(f"Train/test overlap: {len(train_ids & test_ids)} duplicate application_id values.")
    if val_ids & test_ids:
        raise DataLeakageError(f"Val/test overlap: {len(val_ids & test_ids)} duplicate application_id values.")


def assert_enrichment_ignores_label() -> None:
    row = {
        "application_id": "APP-LEAK-001",
        "customer_id": "CUST-1",
        "age": 42,
        "employment_status": "salaried",
        "employment_years": 8.0,
        "monthly_income": 5500.0,
        "monthly_expenses": 3300.0,
        "existing_debt": 24000.0,
        "requested_loan_amount": 45000.0,
        "requested_term_months": 48,
        "loan_purpose": "debt_consolidation",
        "home_ownership": "rent",
        "credit_history_months": 72,
        "prior_defaults": 1,
        "delinquencies_12m": 2,
        "credit_utilization": 0.82,
        "savings_balance": 1800.0,
        "checking_balance": 700.0,
        "num_open_accounts": 6,
        "recent_credit_inquiries": 3,
        "region": "North",
        "channel": "web",
        "collateral_value": 0.0,
        "label_default_12m": 1,
        "target_loss_given_default": 0.65,
    }
    without_label = {k: v for k, v in row.items() if k not in {LABEL_COLUMN, LGD_COLUMN}}
    with_label = dict(row)
    with_label[LABEL_COLUMN] = 0
    with_label[LGD_COLUMN] = 0.05
    enriched_a = enrich_application_row(without_label)
    enriched_b = enrich_application_row(with_label)
    for key in [k for k in enriched_a if k not in row and k not in FORBIDDEN_FEATURE_COLUMNS]:
        if enriched_a.get(key) != enriched_b.get(key):
            raise DataLeakageError(f"Feature '{key}' changes when target columns change.")


def assert_fit_frame_safe(train_frame: pd.DataFrame) -> None:
    feature_columns = [column for column in train_frame.columns if column != LABEL_COLUMN]
    leaked = set(feature_columns) & FORBIDDEN_FEATURE_COLUMNS
    if leaked:
        raise DataLeakageError(f"Forbidden columns in train features: {sorted(leaked)}")
    for column in DROP_FOR_ML:
        if column in feature_columns:
            raise DataLeakageError(f"Column '{column}' must be dropped before fit.")
    if LABEL_COLUMN not in train_frame.columns:
        raise DataLeakageError("Train frame must include label_default_12m as target only.")


def audit_training_inputs(train_rows: list[dict[str, Any]], val_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert_splits_disjoint(train_rows, val_rows, test_rows)
    assert_enrichment_ignores_label()
    train_frame = prepare_ml_frame(train_rows)
    assert_fit_frame_safe(train_frame)
    if len(train_frame) != len(train_rows):
        raise DataLeakageError("Fit frame row count must match train split only.")
    return {
        "status": "ok",
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "test_rows": len(test_rows),
        "train_features": [column for column in train_frame.columns if column != LABEL_COLUMN],
        "dropped_columns": list(DROP_FOR_ML),
        "policy": {
            "fit_data": "train split only",
            "val_used_for": "threshold tuning + validation metrics",
            "test_used_for": "evaluate_test only after training",
            "feature_engineering": "per-row, no label, no LGD target, no global test/val statistics",
        },
    }
