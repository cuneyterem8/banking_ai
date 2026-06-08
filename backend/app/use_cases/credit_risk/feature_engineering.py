from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from app.use_cases.credit_risk.metrics import OPERATIONAL_THRESHOLD
from app.use_cases.credit_risk.risk_prior import (
    credit_default_logit,
    credit_default_logit_components,
    credit_default_probability,
)

LABEL_COLUMN = "label_default_12m"
LGD_COLUMN = "target_loss_given_default"
DROP_FOR_ML = ("application_id", "customer_id", LGD_COLUMN)

EMPLOYMENT_STABILITY = {
    "salaried": 0.85,
    "retired": 0.78,
    "self_employed": 0.62,
    "contract": 0.48,
    "unemployed": 0.12,
}

HOME_STABILITY = {
    "own": 0.9,
    "mortgage": 0.76,
    "family": 0.54,
    "rent": 0.42,
}

PURPOSE_RISK = {
    "auto": 0.28,
    "home_improvement": 0.24,
    "education": 0.36,
    "small_business": 0.56,
    "personal": 0.62,
    "debt_consolidation": 0.7,
}

CHANNEL_RISK = {
    "branch": 0.22,
    "mobile": 0.36,
    "web": 0.42,
    "partner": 0.5,
}


def _row_get(row: dict[str, Any] | pd.Series, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def enrich_application_row(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    income = max(_row_get(row, "monthly_income"), 1.0)
    expenses = _row_get(row, "monthly_expenses")
    debt = _row_get(row, "existing_debt")
    requested = _row_get(row, "requested_loan_amount")
    term = max(_row_get(row, "requested_term_months"), 1.0)
    savings = _row_get(row, "savings_balance")
    checking = _row_get(row, "checking_balance")
    collateral = _row_get(row, "collateral_value")
    credit_history = _row_get(row, "credit_history_months")
    utilization = _row_get(row, "credit_utilization")
    employment_years = _row_get(row, "employment_years")
    delinquencies = _row_get(row, "delinquencies_12m")
    prior_defaults = _row_get(row, "prior_defaults")
    inquiries = _row_get(row, "recent_credit_inquiries")
    open_accounts = max(_row_get(row, "num_open_accounts"), 1.0)
    purpose = str(row.get("loan_purpose", "personal"))
    employment_status = str(row.get("employment_status", "contract"))
    home_ownership = str(row.get("home_ownership", "rent"))
    channel = str(row.get("channel", "web"))

    annual_income = income * 12.0
    payment = requested / term
    dti = debt / max(annual_income, 1.0)
    expense_ratio = expenses / income
    payment_to_income = payment / income
    loan_to_income = requested / max(annual_income, 1.0)
    collateral_coverage = collateral / max(requested, 1.0)
    liquid_months = (savings + checking) / max(expenses, 1.0)
    history_years = credit_history / 12.0
    stability = EMPLOYMENT_STABILITY.get(employment_status, 0.45)
    home_stability = HOME_STABILITY.get(home_ownership, 0.45)
    purpose_risk = PURPOSE_RISK.get(purpose, 0.5)
    channel_risk = CHANNEL_RISK.get(channel, 0.4)
    prior_components = credit_default_logit_components(row)
    prior_logit = credit_default_logit(row, include_intercept=True)
    prior_prob = credit_default_probability(row)

    affordability_risk = _clamp01(
        0.34 * min(dti, 1.2)
        + 0.28 * min(payment_to_income, 1.0)
        + 0.2 * min(expense_ratio, 1.2)
        + 0.18 * utilization
    )
    credit_behavior_risk = _clamp01(
        0.28 * min(delinquencies / 5.0, 1.0)
        + 0.28 * min(prior_defaults / 2.0, 1.0)
        + 0.18 * min(inquiries / 6.0, 1.0)
        + 0.14 * (1.0 if history_years < 2.0 else 0.0)
        + 0.12 * utilization
    )
    stability_gap = _clamp01(1.0 - (0.55 * stability + 0.45 * home_stability))

    enriched.update(
        {
            "annual_income": round(annual_income, 2),
            "estimated_monthly_payment": round(payment, 2),
            "debt_to_income_ratio": round(dti, 4),
            "expense_ratio": round(expense_ratio, 4),
            "payment_to_income_ratio": round(payment_to_income, 4),
            "loan_to_income_ratio": round(loan_to_income, 4),
            "collateral_coverage": round(collateral_coverage, 4),
            "liquid_reserve_months": round(liquid_months, 4),
            "credit_history_years": round(history_years, 4),
            "employment_stability_score": round(stability, 4),
            "home_stability_score": round(home_stability, 4),
            "purpose_risk_score": round(purpose_risk, 4),
            "channel_risk_score": round(channel_risk, 4),
            "affordability_risk": round(affordability_risk, 4),
            "credit_behavior_risk": round(credit_behavior_risk, 4),
            "stability_gap": round(stability_gap, 4),
            "high_utilization": 1 if utilization >= 0.75 else 0,
            "thin_file": 1 if credit_history < 24 else 0,
            "recent_inquiry_pressure": round(min(inquiries / max(open_accounts, 1.0), 2.0), 4),
            "delinquency_density": round(delinquencies / max(open_accounts, 1.0), 4),
            "collateral_gap": round(_clamp01(1.0 - min(collateral_coverage, 1.0)), 4),
            "default_history_flag": 1 if prior_defaults > 0 else 0,
            "low_liquidity_flag": 1 if liquid_months < 1.5 else 0,
            "unsecured_high_amount": 1 if collateral_coverage < 0.25 and loan_to_income > 0.45 else 0,
            "debt_consolidation_flag": 1 if purpose == "debt_consolidation" else 0,
            "small_business_flag": 1 if purpose == "small_business" else 0,
            "digital_channel_flag": 1 if channel in {"mobile", "web", "partner"} else 0,
            "prior_default_utilization": round(min(prior_defaults * utilization, 3.0), 4),
            "dti_utilization_interaction": round(min(dti * utilization, 2.0), 4),
            "payment_stability_interaction": round(payment_to_income * stability_gap, 4),
            "prior_default_probability": round(prior_prob, 4),
            "prior_default_logit": round(prior_logit, 4),
            **{key: round(value, 4) for key, value in prior_components.items()},
        }
    )
    return enriched


def enrich_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_application_row(row) for row in rows]


def prepare_ml_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(enrich_rows(rows))
    for column in DROP_FOR_ML:
        if column in frame.columns:
            frame = frame.drop(columns=[column])
    return frame


def threshold_file(model_dir: Path) -> Path:
    return Path(model_dir) / "operational_threshold.json"


def save_operational_threshold(model_dir: Path, threshold: float) -> None:
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    threshold_file(model_dir).write_text(json.dumps({"threshold": round(float(threshold), 4)}), encoding="utf-8")


def load_operational_threshold(model_dir: Path) -> float:
    path = threshold_file(model_dir)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("threshold", OPERATIONAL_THRESHOLD))
    return OPERATIONAL_THRESHOLD
