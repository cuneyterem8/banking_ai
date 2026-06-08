"""Shared credit default prior formula (features only; never reads label_default_12m)."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

LOGIT_BASE = -2.35
SIGNAL_SCALE = 1.08


@lru_cache(maxsize=1)
def credit_logit_intercept_adjust() -> float:
    from app.use_cases.credit_risk.data_generation import credit_metadata_path

    path = credit_metadata_path()
    if not path.exists():
        return 0.0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload.get("default_logit_intercept", 0.0))


def _dti(row: dict[str, Any]) -> float:
    income = max(float(row["monthly_income"]), 1.0)
    return float(row["existing_debt"]) / (income * 12.0)


def _pti(row: dict[str, Any]) -> float:
    income = max(float(row["monthly_income"]), 1.0)
    monthly_payment = float(row["requested_loan_amount"]) / max(float(row["requested_term_months"]), 1.0)
    return monthly_payment / income


def credit_default_logit_components(row: dict[str, Any]) -> dict[str, float]:
    dti = _dti(row)
    pti = _pti(row)
    savings_months = float(row["savings_balance"]) / max(float(row["monthly_expenses"]), 1.0)
    collateral_coverage = float(row["collateral_value"]) / max(float(row["requested_loan_amount"]), 1.0)
    credit_history_years = float(row["credit_history_months"]) / 12.0
    employment_years = float(row["employment_years"])
    s = SIGNAL_SCALE
    return {
        "prior_term_dti": s * 2.0 * min(dti, 1.3),
        "prior_term_pti": s * 1.65 * min(pti, 1.0),
        "prior_term_utilization": s * 1.4 * float(row["credit_utilization"]),
        "prior_term_delinquency": s * 0.34 * float(row["delinquencies_12m"]),
        "prior_term_defaults": s * 0.9 * float(row["prior_defaults"]),
        "prior_term_inquiries": s * 0.18 * float(row["recent_credit_inquiries"]),
        "prior_term_short_history": s * 0.42 * (1.0 if credit_history_years < 2 else 0.0),
        "prior_term_unstable_work": s * 0.4 * (1.0 if employment_years < 1 else 0.0),
        "prior_term_low_savings": s * 0.35 * (1.0 if savings_months < 1.5 else 0.0),
        "prior_term_no_collateral": s * 0.3 * (1.0 if collateral_coverage < 0.25 else 0.0),
        "prior_term_unsecured": s * 0.28 * (1.0 if row.get("loan_purpose") in {"personal", "debt_consolidation"} else 0.0),
        "prior_term_renter": s * 0.22 * (1.0 if row.get("home_ownership") == "rent" else 0.0),
    }


def credit_default_logit(row: dict[str, Any], *, include_intercept: bool = True) -> float:
    logit = LOGIT_BASE + sum(credit_default_logit_components(row).values())
    if include_intercept:
        logit += credit_logit_intercept_adjust()
    return logit


def credit_default_probability(row: dict[str, Any]) -> float:
    logit = credit_default_logit(row, include_intercept=True)
    if logit >= 0:
        z = math.exp(-logit)
        return 1.0 / (1.0 + z)
    z = math.exp(logit)
    return z / (1.0 + z)
