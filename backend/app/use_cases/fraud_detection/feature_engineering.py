"""Derive teachable fraud signals from raw transaction fields (train + inference)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from app.use_cases.fraud_detection.metrics import OPERATIONAL_THRESHOLD
from app.use_cases.fraud_detection.risk_prior import (
    fraud_risk_logit,
    fraud_risk_logit_components,
    fraud_risk_probability,
)

LABEL_COLUMN = "label_is_fraud"

DROP_FOR_ML = ("transaction_id", "merchant_id", "customer_id")

CHANNEL_RISK_SCORES = {
    "card_present": 0.12,
    "ecommerce": 0.32,
    "mobile_transfer": 0.42,
    "atm": 0.28,
    "wire": 0.58,
}

AUTH_STRENGTH = {
    "pin": 0.85,
    "biometric": 0.95,
    "otp": 0.72,
    "none": 0.05,
}

DEVICE_OS_RISK = {
    "ios": 0.15,
    "android": 0.18,
    "web": 0.35,
    "unknown": 0.55,
}

HIGH_RISK_MERCHANTS = {"gambling", "crypto_exchange", "cash_transfer", "luxury"}
ECOMMERCE_CHANNELS = {"ecommerce", "mobile_transfer"}


def _row_get(row: dict[str, Any] | pd.Series, key: str, default: float = 0.0) -> float:
    if isinstance(row, pd.Series):
        value = row.get(key, default)
    else:
        value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def enrich_transaction_row(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    avg_30d = max(_row_get(row, "avg_30d_amount"), 1.0)
    balance = max(_row_get(row, "account_balance_before"), 1.0)
    amount = _row_get(row, "amount")
    device_trust = _row_get(row, "device_trust_score")
    ip_risk = _row_get(row, "ip_risk_score")
    merchant_risk = _row_get(row, "merchant_risk_score")
    failed_logins = _row_get(row, "failed_login_count_24h")
    velocity = _row_get(row, "velocity_24h_count")
    distance = _row_get(row, "distance_from_home_km")
    is_international = int(_row_get(row, "is_international"))
    is_new_payee = int(_row_get(row, "is_new_payee"))
    prior_chargebacks = int(_row_get(row, "prior_chargebacks"))
    hour = int(_row_get(row, "hour_of_day"))
    account_age = int(_row_get(row, "account_age_days"))
    days_since_last = int(_row_get(row, "days_since_last_transaction"))
    session_minutes = max(_row_get(row, "session_duration_minutes"), 1.0)
    auth_method = str(row.get("auth_method", ""))
    category = str(row.get("merchant_category", ""))
    channel = str(row.get("channel", ""))
    device_os = str(row.get("device_os", "unknown"))
    transaction_type = str(row.get("transaction_type", ""))

    amount_ratio = amount / avg_30d
    log_amount = math.log1p(amount)
    device_stress = 1.0 - device_trust
    amount_ratio_capped = min(amount_ratio, 12.0)

    device_ip_risk = device_stress * ip_risk
    login_velocity_risk = _clamp01((failed_logins / 6.0) + (velocity / 16.0))
    geo_risk = _clamp01((0.35 if is_international else 0.05) + math.log1p(distance) / 12.0)
    night_transaction = 1 if hour < 5 or hour >= 23 else 0
    weekend_transaction = 1 if hour >= 22 else 0
    weak_auth = 1 if auth_method == "none" else 0
    high_risk_merchant = 1 if category in HIGH_RISK_MERCHANTS else 0
    channel_risk_score = CHANNEL_RISK_SCORES.get(channel, 0.3)
    trust_merchant_risk = device_stress * merchant_risk
    amount_ip_interaction = _clamp01(amount_ratio_capped * ip_risk / 4.0)
    auth_strength = AUTH_STRENGTH.get(auth_method, 0.4)
    auth_gap = 1.0 - auth_strength
    device_os_risk = DEVICE_OS_RISK.get(device_os, 0.4)
    ecommerce_channel = 1 if channel in ECOMMERCE_CHANNELS else 0

    prior_components = fraud_risk_logit_components(row)
    prior_logit = fraud_risk_logit(row, include_intercept=True)
    prior_prob = fraud_risk_probability(row)

    # Behavioral composites (weights differ from label noise layer — not a label clone).
    behavioral_risk_index = _clamp01(
        0.22 * geo_risk
        + 0.2 * login_velocity_risk
        + 0.18 * device_ip_risk
        + 0.14 * trust_merchant_risk
        + 0.12 * _clamp01(amount_ratio_capped / 6.0)
        + 0.08 * auth_gap
        + 0.06 * channel_risk_score
    )
    anomaly_session_score = _clamp01((12.0 / session_minutes) * _clamp01(amount_ratio_capped / 4.0))
    dormant_reactivation = _clamp01(math.log1p(days_since_last) / 4.0 * _clamp01(amount_ratio_capped / 5.0))
    young_account_flag = 1 if account_age < 120 else 0
    balance_stress = _clamp01(amount / balance)

    enriched.update(
        {
            # Core ratios
            "amount_ratio": round(amount_ratio, 4),
            "log_amount": round(log_amount, 4),
            "amount_vs_balance": round(amount / balance, 4),
            "amount_ratio_sq": round(min(amount_ratio_capped**2, 144.0), 4),
            "sqrt_amount_ratio": round(math.sqrt(amount_ratio_capped), 4),
            # Network / device
            "device_ip_risk": round(device_ip_risk, 4),
            "trust_merchant_risk": round(trust_merchant_risk, 4),
            "amount_ip_interaction": round(amount_ip_interaction, 4),
            "ip_merchant_risk": round(ip_risk * merchant_risk, 4),
            "device_velocity_stress": round(device_stress * login_velocity_risk, 4),
            "device_os_risk": round(device_os_risk, 4),
            # Behaviour / time
            "login_velocity_risk": round(login_velocity_risk, 4),
            "geo_risk": round(geo_risk, 4),
            "distance_log": round(math.log1p(distance), 4),
            "channel_risk_score": round(channel_risk_score, 4),
            "night_transaction": night_transaction,
            "weekend_transaction": weekend_transaction,
            "weak_auth": weak_auth,
            "auth_strength": round(auth_strength, 4),
            "auth_gap": round(auth_gap, 4),
            "high_risk_merchant": high_risk_merchant,
            "wire_channel": 1 if channel == "wire" else 0,
            "ecommerce_channel": ecommerce_channel,
            "transfer_type": 1 if transaction_type in {"transfer", "withdrawal"} else 0,
            # Prior decomposition (aligned with DGP structure, no label access)
            "prior_risk_probability": round(prior_prob, 4),
            "prior_risk_logit": round(prior_logit, 4),
            **{key: round(value, 4) for key, value in prior_components.items()},
            # Interactions
            "international_wire": is_international * (1 if channel == "wire" else 0),
            "velocity_amount_risk": round(_clamp01(login_velocity_risk * amount_ratio_capped / 6.0), 4),
            "login_amount_risk": round(_clamp01((failed_logins / 5.0) * amount_ratio_capped / 4.0), 4),
            "night_high_amount": night_transaction * (1 if amount_ratio_capped > 2.5 else 0),
            "new_payee_high_amount": is_new_payee * (1 if amount_ratio_capped > 2.0 else 0),
            "new_payee_wire": is_new_payee * (1 if channel == "wire" else 0),
            "chargeback_velocity": round(_clamp01(prior_chargebacks * login_velocity_risk), 4),
            "weak_auth_high_amount": weak_auth * (1 if amount_ratio_capped > 1.8 else 0),
            "international_high_ip": is_international * (1 if ip_risk > 0.55 else 0),
            "merchant_channel_risk": round(channel_risk_score * merchant_risk, 4),
            "geo_amount_risk": round(geo_risk * _clamp01(log_amount / 8.0), 4),
            "amt_trust_ip_triple": round(
                _clamp01(amount_ratio_capped * device_stress * ip_risk / 5.0), 4
            ),
            "prior_times_amount": round(prior_prob * _clamp01(amount_ratio_capped / 4.0), 4),
            # Composite indices
            "behavioral_risk_index": round(behavioral_risk_index, 4),
            "anomaly_session_score": round(anomaly_session_score, 4),
            "dormant_reactivation": round(dormant_reactivation, 4),
            "young_account_flag": young_account_flag,
            "balance_stress": round(balance_stress, 4),
            "account_age_log": round(math.log1p(account_age), 4),
            "velocity_sq": round((velocity**2) / 100.0, 4),
        }
    )
    return enriched


def enrich_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_transaction_row(row) for row in rows]


def prepare_ml_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    enriched = enrich_rows(rows)
    frame = pd.DataFrame(enriched)
    for column in DROP_FOR_ML:
        if column in frame.columns:
            frame = frame.drop(columns=[column])
    return frame


def threshold_file(model_dir: Path) -> Path:
    return Path(model_dir) / "operational_threshold.json"


def save_operational_threshold(model_dir: Path, threshold: float) -> None:
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    threshold_file(model_dir).write_text(
        json.dumps({"threshold": round(float(threshold), 4)}),
        encoding="utf-8",
    )


def load_operational_threshold(model_dir: Path) -> float:
    path = threshold_file(model_dir)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("threshold", OPERATIONAL_THRESHOLD))
    return OPERATIONAL_THRESHOLD
