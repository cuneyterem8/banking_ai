from app.use_cases.fraud_detection.metrics import PRIMARY_METRIC, PRIMARY_METRIC_LABEL
from app.use_cases.fraud_detection.training import evaluate_split


class _StubPredictor:
    def predict_proba(self, frame):
        import pandas as pd

        scores = []
        for _, row in frame.iterrows():
            score = 0.15
            if row.get("device_trust_score", 1) < 0.4:
                score += 0.45
            if row.get("ip_risk_score", 0) > 0.6:
                score += 0.35
            scores.append(min(score, 0.99))
        return pd.DataFrame({0: [1 - s for s in scores], 1: scores})


def test_primary_metric_is_pr_auc() -> None:
    assert PRIMARY_METRIC == "average_precision"
    assert PRIMARY_METRIC_LABEL == "PR-AUC"


def test_evaluate_split_exposes_primary_and_threshold_metrics() -> None:
    rows = [
        {
            "transaction_id": "TXN-000001",
            "customer_id": "CUST-1000",
            "account_age_days": 400,
            "amount": 120.0,
            "currency": "USD",
            "merchant_id": "MRC-10001",
            "merchant_category": "grocery",
            "merchant_risk_score": 0.12,
            "channel": "card_present",
            "transaction_type": "purchase",
            "card_type": "debit",
            "country": "US",
            "is_international": 0,
            "device_trust_score": 0.82,
            "ip_risk_score": 0.1,
            "auth_method": "pin",
            "device_os": "ios",
            "session_duration_minutes": 12,
            "failed_login_count_24h": 0,
            "velocity_24h_count": 2,
            "days_since_last_transaction": 1,
            "prior_chargebacks": 0,
            "hour_of_day": 14,
            "is_new_payee": 0,
            "distance_from_home_km": 5.0,
            "avg_30d_amount": 95.0,
            "account_balance_before": 800.0,
            "label_is_fraud": 0,
        },
        {
            "transaction_id": "TXN-000002",
            "customer_id": "CUST-1001",
            "account_age_days": 90,
            "amount": 2400.0,
            "currency": "USD",
            "merchant_id": "MRC-10002",
            "merchant_category": "crypto_exchange",
            "merchant_risk_score": 0.88,
            "channel": "wire",
            "transaction_type": "transfer",
            "card_type": "credit",
            "country": "SG",
            "is_international": 1,
            "device_trust_score": 0.18,
            "ip_risk_score": 0.82,
            "auth_method": "none",
            "device_os": "unknown",
            "session_duration_minutes": 2,
            "failed_login_count_24h": 4,
            "velocity_24h_count": 11,
            "days_since_last_transaction": 20,
            "prior_chargebacks": 2,
            "hour_of_day": 3,
            "is_new_payee": 1,
            "distance_from_home_km": 5200.0,
            "avg_30d_amount": 180.0,
            "account_balance_before": 120.0,
            "label_is_fraud": 1,
        },
    ]

    evaluation = evaluate_split(_StubPredictor(), rows, split_name="val")
    assert evaluation.primary_metric == "average_precision"
    assert evaluation.primary_metric_label == "PR-AUC"
    assert evaluation.primary_score is not None
    assert 0 <= evaluation.primary_score <= 1
    assert 0 <= evaluation.precision <= 1
    assert 0 <= evaluation.recall <= 1
    assert len(evaluation.pr_curve) >= 2
