from app.use_cases.credit_risk.metrics import PRIMARY_METRIC, PRIMARY_METRIC_LABEL
from app.use_cases.credit_risk.training import evaluate_split


class _StubPredictor:
    def predict_proba(self, frame):
        import pandas as pd

        scores = []
        for _, row in frame.iterrows():
            score = 0.08
            if row.get("credit_utilization", 0) > 0.75:
                score += 0.35
            if row.get("delinquencies_12m", 0) >= 2:
                score += 0.35
            scores.append(min(score, 0.98))
        return pd.DataFrame({0: [1 - score for score in scores], 1: scores})


def test_credit_primary_metric_is_roc_auc() -> None:
    assert PRIMARY_METRIC == "roc_auc"
    assert PRIMARY_METRIC_LABEL == "ROC-AUC"


def test_credit_evaluate_split_exposes_metrics() -> None:
    rows = [
        {
            "application_id": "APP-000001",
            "customer_id": "CUST-5000",
            "age": 44,
            "employment_status": "salaried",
            "employment_years": 9.0,
            "monthly_income": 6800.0,
            "monthly_expenses": 3500.0,
            "existing_debt": 12000.0,
            "requested_loan_amount": 25000.0,
            "requested_term_months": 36,
            "loan_purpose": "auto",
            "home_ownership": "mortgage",
            "credit_history_months": 132,
            "prior_defaults": 0,
            "delinquencies_12m": 0,
            "credit_utilization": 0.31,
            "savings_balance": 16000.0,
            "checking_balance": 3800.0,
            "num_open_accounts": 5,
            "recent_credit_inquiries": 1,
            "region": "West",
            "channel": "branch",
            "collateral_value": 22000.0,
            "label_default_12m": 0,
            "target_loss_given_default": 0.18,
        },
        {
            "application_id": "APP-000002",
            "customer_id": "CUST-5001",
            "age": 29,
            "employment_status": "contract",
            "employment_years": 0.4,
            "monthly_income": 3300.0,
            "monthly_expenses": 3000.0,
            "existing_debt": 52000.0,
            "requested_loan_amount": 72000.0,
            "requested_term_months": 48,
            "loan_purpose": "debt_consolidation",
            "home_ownership": "rent",
            "credit_history_months": 14,
            "prior_defaults": 1,
            "delinquencies_12m": 4,
            "credit_utilization": 0.94,
            "savings_balance": 300.0,
            "checking_balance": 120.0,
            "num_open_accounts": 8,
            "recent_credit_inquiries": 5,
            "region": "North",
            "channel": "web",
            "collateral_value": 0.0,
            "label_default_12m": 1,
            "target_loss_given_default": 0.74,
        },
    ]
    evaluation = evaluate_split(_StubPredictor(), rows, split_name="val")
    assert evaluation.primary_metric == "roc_auc"
    assert evaluation.primary_score is not None
    assert 0 <= evaluation.precision <= 1
    assert len(evaluation.records) == 2
