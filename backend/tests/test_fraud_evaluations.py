from sqlmodel import Session

from app.db.models import ModelRun, ProcessedResult
from app.use_cases.fraud_detection.service import (
    FRAUD_TEST_RESULT_TYPE,
    FRAUD_VAL_RESULT_TYPE,
    get_fraud_evaluations,
)
from app.use_cases.fraud_detection.raw_data import USE_CASE_SLUG


def _sample_evaluation(split: str) -> dict:
    return {
        "split": split,
        "record_count": 2,
        "primary_metric": "average_precision",
        "primary_metric_label": "PR-AUC",
        "primary_score": 0.42,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "accuracy": 0.5,
        "roc_auc": 0.55,
        "threshold": 0.5,
        "correct_predictions": 1,
        "confusion_matrix": {"tp": 1, "tn": 0, "fp": 1, "fn": 0},
        "pr_curve": [],
        "roc_curve": [],
        "records": [
            {
                "transaction_id": "TXN-000001",
                "customer_id": "CUST-1000",
                "amount": 10.0,
                "actual_is_fraud": 1,
                "predicted_is_fraud": 1,
                "fraud_probability": 0.8,
                "risk_level": "High",
                "decision": "Block and review",
                "top_factors": ["test"],
            }
        ],
    }


def test_get_fraud_evaluations_returns_latest_val_and_test(session: Session) -> None:
    val_run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="completed",
        metrics={"split": "val"},
    )
    test_run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="completed",
        metrics={"split": "test"},
    )
    session.add(val_run)
    session.add(test_run)
    session.commit()
    session.refresh(val_run)
    session.refresh(test_run)

    session.add(
        ProcessedResult(
            run_id=val_run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=FRAUD_VAL_RESULT_TYPE,
            payload={"split": "val", "evaluation": _sample_evaluation("val")},
            explanation={},
        )
    )
    session.add(
        ProcessedResult(
            run_id=test_run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=FRAUD_TEST_RESULT_TYPE,
            payload={"split": "test", "evaluation": _sample_evaluation("test")},
            explanation={},
        )
    )
    session.commit()

    payload = get_fraud_evaluations(session)
    assert payload["val"] is not None
    assert payload["val"]["evaluation"]["split"] == "val"
    assert payload["val"]["evaluation"]["primary_score"] == 0.42
    assert payload["test"] is not None
    assert payload["test"]["evaluation"]["split"] == "test"


def test_get_fraud_evaluations_empty_when_no_results(session: Session) -> None:
    payload = get_fraud_evaluations(session)
    assert payload["val"] is None
    assert payload["test"] is None
