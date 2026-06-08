"""Shared risk prior formula (features only — never reads label_is_fraud)."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

# Slightly stronger than baseline so models can reach PR-AUC ~0.32+ without extreme val/test drift.
LOGIT_BASE = -2.68
SIGNAL_SCALE = 1.14


@lru_cache(maxsize=1)
def fraud_logit_intercept_adjust() -> float:
    """Population intercept from data generation (matches label DGP, not labels themselves)."""
    from app.use_cases.fraud_detection.data_generation import fraud_metadata_path

    path = fraud_metadata_path()
    if not path.exists():
        return 0.0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload.get("fraud_logit_intercept", 0.0))


def _amount_ratio(row: dict[str, Any]) -> float:
    return float(row["amount"]) / max(float(row["avg_30d_amount"]), 1.0)


def fraud_risk_logit_components(row: dict[str, Any]) -> dict[str, float]:
    """Decomposed logit terms (same structure as label DGP, without intercept or label noise)."""
    amount_ratio = _amount_ratio(row)
    s = SIGNAL_SCALE
    return {
        "prior_term_amount": s * 0.62 * math.log1p(amount_ratio),
        "prior_term_ip": s * 1.45 * float(row["ip_risk_score"]),
        "prior_term_device": s * 1.15 * (1.0 - float(row["device_trust_score"])),
        "prior_term_merchant": s * 0.82 * float(row["merchant_risk_score"]),
        "prior_term_login": s * 0.24 * float(row["failed_login_count_24h"]),
        "prior_term_velocity": s * 0.14 * float(row["velocity_24h_count"]),
        "prior_term_new_payee": s * 0.42 * float(row["is_new_payee"]),
        "prior_term_distance": s * 0.32 * min(float(row["distance_from_home_km"]) / 800.0, 2.5),
        "prior_term_international": s * 0.38 * float(row["is_international"]),
        "prior_term_chargeback": s * 0.68 * float(row["prior_chargebacks"]),
        "prior_term_weak_auth": s * 0.32 * (1.0 if row.get("auth_method") == "none" else 0.0),
        "prior_term_night": s * 0.16 * (1.0 if int(row["hour_of_day"]) < 5 else 0.0),
        "prior_term_wire": s * 0.22 * (1.0 if row.get("channel") == "wire" else 0.0),
    }


def fraud_risk_logit(row: dict[str, Any], *, include_intercept: bool = True) -> float:
    logit = LOGIT_BASE + sum(fraud_risk_logit_components(row).values())
    if include_intercept:
        logit += fraud_logit_intercept_adjust()
    return logit


def fraud_risk_probability(row: dict[str, Any]) -> float:
    logit = fraud_risk_logit(row, include_intercept=True)
    if logit >= 0:
        z = math.exp(-logit)
        return 1.0 / (1.0 + z)
    z = math.exp(logit)
    return z / (1.0 + z)
