from app.use_cases.fraud_detection.feature_engineering import enrich_transaction_row, prepare_ml_frame
from app.use_cases.fraud_detection.threshold_tuning import find_best_f1_threshold


def _sample_row() -> dict:
    return {
        "transaction_id": "TXN-000001",
        "customer_id": "CUST-1000",
        "account_age_days": 400,
        "amount": 900.0,
        "currency": "USD",
        "merchant_id": "MRC-10001",
        "merchant_category": "crypto_exchange",
        "merchant_risk_score": 0.82,
        "channel": "wire",
        "transaction_type": "transfer",
        "card_type": "credit",
        "country": "SG",
        "is_international": 1,
        "device_trust_score": 0.2,
        "ip_risk_score": 0.78,
        "auth_method": "none",
        "device_os": "unknown",
        "session_duration_minutes": 3,
        "failed_login_count_24h": 4,
        "velocity_24h_count": 10,
        "days_since_last_transaction": 12,
        "prior_chargebacks": 1,
        "hour_of_day": 2,
        "is_new_payee": 1,
        "distance_from_home_km": 4200.0,
        "avg_30d_amount": 120.0,
        "account_balance_before": 300.0,
        "label_is_fraud": 1,
    }


def test_enrich_transaction_row_adds_engineered_signals() -> None:
    enriched = enrich_transaction_row(_sample_row())
    assert enriched["amount_ratio"] > 3
    assert enriched["device_ip_risk"] > 0.3
    assert enriched["amount_ip_interaction"] > 0
    assert enriched["weak_auth"] == 1
    assert enriched["prior_risk_logit"] > 0
    assert enriched["prior_term_ip"] > 0
    assert enriched["behavioral_risk_index"] > 0.2
    assert enriched["amt_trust_ip_triple"] > 0
    assert "composite_risk_score" not in enriched
    assert "transaction_id" in enriched


def test_prepare_ml_frame_drops_high_cardinality_ids() -> None:
    frame = prepare_ml_frame([_sample_row()])
    assert "transaction_id" not in frame.columns
    assert "merchant_id" not in frame.columns
    assert "device_ip_risk" in frame.columns
    assert "composite_risk_score" not in frame.columns


def test_find_best_f1_threshold_prefers_separating_scores() -> None:
    y_true = [0, 0, 0, 1, 1, 1]
    scores = [0.1, 0.2, 0.25, 0.7, 0.8, 0.9]
    threshold = find_best_f1_threshold(y_true, scores)
    assert 0.2 <= threshold <= 0.75
