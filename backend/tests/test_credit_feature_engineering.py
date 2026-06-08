from app.use_cases.credit_risk.feature_engineering import enrich_application_row, prepare_ml_frame
from app.use_cases.credit_risk.threshold_tuning import find_best_f1_threshold


def _sample_row() -> dict:
    return {
        "application_id": "APP-000001",
        "customer_id": "CUST-5000",
        "age": 39,
        "employment_status": "contract",
        "employment_years": 0.7,
        "monthly_income": 4200.0,
        "monthly_expenses": 3400.0,
        "existing_debt": 47000.0,
        "requested_loan_amount": 68000.0,
        "requested_term_months": 48,
        "loan_purpose": "debt_consolidation",
        "home_ownership": "rent",
        "credit_history_months": 18,
        "prior_defaults": 1,
        "delinquencies_12m": 3,
        "credit_utilization": 0.91,
        "savings_balance": 500.0,
        "checking_balance": 250.0,
        "num_open_accounts": 7,
        "recent_credit_inquiries": 4,
        "region": "North",
        "channel": "web",
        "collateral_value": 0.0,
        "label_default_12m": 1,
        "target_loss_given_default": 0.72,
    }


def test_enrich_application_row_adds_credit_signals() -> None:
    enriched = enrich_application_row(_sample_row())
    assert enriched["debt_to_income_ratio"] > 0.5
    assert enriched["payment_to_income_ratio"] > 0.2
    assert enriched["affordability_risk"] > 0.3
    assert enriched["credit_behavior_risk"] > 0.4
    assert enriched["thin_file"] == 1
    assert enriched["default_history_flag"] == 1


def test_prepare_ml_frame_drops_ids_and_lgd_target() -> None:
    frame = prepare_ml_frame([_sample_row()])
    assert "application_id" not in frame.columns
    assert "customer_id" not in frame.columns
    assert "target_loss_given_default" not in frame.columns
    assert "label_default_12m" in frame.columns
    assert "affordability_risk" in frame.columns


def test_credit_threshold_prefers_separating_scores() -> None:
    y_true = [0, 0, 0, 1, 1, 1]
    scores = [0.08, 0.14, 0.22, 0.55, 0.73, 0.88]
    threshold = find_best_f1_threshold(y_true, scores)
    assert 0.2 <= threshold <= 0.75
