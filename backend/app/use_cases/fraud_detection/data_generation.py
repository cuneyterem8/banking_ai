import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.data_paths import get_use_case_data_dir
from app.use_cases.fraud_detection.risk_prior import fraud_risk_logit


USE_CASE_SLUG = "fraud-detection"
FILE_BASENAME = "synthetic_fraud_transactions"
TRAIN_POOL_COUNT = 3200
ML_TRAIN_COUNT = 2560
ML_VAL_COUNT = 640
TEST_COUNT = 800
TOTAL_COUNT = TRAIN_POOL_COUNT + TEST_COUNT
GENERATION_SEED = 4521
VAL_SPLIT_RATIO = 0.2

# Target overall fraud prevalence (card-not-present portfolios are often low single digits).
TARGET_FRAUD_RATE = 0.075
LABEL_NOISE_RATE = 0.003
LABEL_LOGIT_NOISE_STD = 0.09
FRAUD_CAMOUFLAGE_RATE = 0.012
LEGIT_RISKY_DECOY_RATE = 0.02

HEADERS = [
    "transaction_id",
    "customer_id",
    "account_age_days",
    "amount",
    "currency",
    "merchant_id",
    "merchant_category",
    "merchant_risk_score",
    "channel",
    "transaction_type",
    "card_type",
    "country",
    "is_international",
    "device_trust_score",
    "ip_risk_score",
    "auth_method",
    "device_os",
    "session_duration_minutes",
    "failed_login_count_24h",
    "velocity_24h_count",
    "days_since_last_transaction",
    "prior_chargebacks",
    "hour_of_day",
    "is_new_payee",
    "distance_from_home_km",
    "avg_30d_amount",
    "account_balance_before",
    "label_is_fraud",
]

MERCHANTS = [
    "grocery",
    "electronics",
    "travel",
    "fuel",
    "online_marketplace",
    "luxury",
    "cash_transfer",
    "gambling",
    "crypto_exchange",
    "pharmacy",
]
LOW_RISK_MERCHANTS = {"grocery", "fuel", "pharmacy"}
HIGH_RISK_MERCHANTS = {"gambling", "crypto_exchange", "cash_transfer", "luxury"}
CHANNELS = ["card_present", "ecommerce", "mobile_transfer", "atm", "wire"]
COUNTRIES = ["US", "GB", "DE", "TR", "NL", "SG", "BR", "FR", "ES", "CA"]
CARD_TYPES = ["debit", "credit", "prepaid"]
TRANSACTION_TYPES = ["purchase", "refund", "transfer", "withdrawal"]
AUTH_METHODS = ["pin", "biometric", "otp", "none"]
DEVICE_OS = ["ios", "android", "web", "unknown"]
CURRENCIES = ["USD", "EUR", "GBP", "TRY"]


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    account_age_days: int
    home_country: str
    currency: str
    avg_30d_amount: float
    account_balance_before: float
    device_trust_baseline: float
    prior_chargebacks: int
    spend_volatility: float
    travel_frequency: float


def fraud_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def fraud_metadata_path() -> Path:
    return fraud_data_root() / "metadata.json"


def fraud_split_dir(split: str) -> Path:
    return fraud_data_root() / "raw" / split


def fraud_xlsx_path(split: str) -> Path:
    return fraud_split_dir(split) / f"{FILE_BASENAME}.xlsx"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def _merchant_risk_for_category(category: str, rng: random.Random) -> float:
    if category in LOW_RISK_MERCHANTS:
        return round(rng.uniform(0.04, 0.28), 3)
    if category in HIGH_RISK_MERCHANTS:
        return round(rng.uniform(0.45, 0.88), 3)
    return round(rng.uniform(0.18, 0.55), 3)


def _build_customer_profiles(customer_count: int, rng: random.Random) -> dict[str, CustomerProfile]:
    profiles: dict[str, CustomerProfile] = {}
    for index in range(customer_count):
        customer_id = f"CUST-{1000 + index}"
        account_age_days = int(rng.expovariate(1 / 1400) + 30)
        account_age_days = min(account_age_days, 7200)
        home_country = rng.choice(COUNTRIES)
        currency = rng.choice(CURRENCIES)
        spend_band = rng.random()
        if spend_band < 0.55:
            avg_30d_amount = round(rng.uniform(25, 180), 2)
        elif spend_band < 0.9:
            avg_30d_amount = round(rng.uniform(150, 650), 2)
        else:
            avg_30d_amount = round(rng.uniform(500, 2200), 2)

        profiles[customer_id] = CustomerProfile(
            customer_id=customer_id,
            account_age_days=account_age_days,
            home_country=home_country,
            currency=currency,
            avg_30d_amount=avg_30d_amount,
            account_balance_before=round(avg_30d_amount * rng.uniform(0.4, 8.5), 2),
            device_trust_baseline=round(rng.betavariate(5, 2) * 0.55 + 0.35, 3),
            prior_chargebacks=1 if rng.random() < 0.07 else 0,
            spend_volatility=rng.uniform(0.35, 1.8),
            travel_frequency=rng.uniform(0.02, 0.35),
        )
    return profiles


def _sample_transaction_features(profile: CustomerProfile, rng: random.Random) -> dict[str, Any]:
    """Sample observables with heavy overlap between eventual fraud and legitimate behaviour."""
    category = rng.choices(
        MERCHANTS,
        weights=[22, 14, 10, 12, 16, 5, 4, 3, 2, 12],
        k=1,
    )[0]
    channel = rng.choices(
        CHANNELS,
        weights=[30, 28, 18, 14, 10],
        k=1,
    )[0]

    amount_multiplier = rng.lognormvariate(0, profile.spend_volatility * 0.45)
    if channel == "wire":
        amount_multiplier *= rng.uniform(1.2, 3.5)
    if category in HIGH_RISK_MERCHANTS:
        amount_multiplier *= rng.uniform(0.8, 2.2)

    amount = round(profile.avg_30d_amount * amount_multiplier, 2)
    amount = max(1.5, min(amount, profile.avg_30d_amount * 12))

    is_international = 1 if rng.random() < profile.travel_frequency else 0
    if is_international and rng.random() < 0.35:
        country = rng.choice([c for c in COUNTRIES if c != profile.home_country])
    else:
        country = profile.home_country

    device_trust_score = round(
        _clamp(
            rng.gauss(profile.device_trust_baseline, 0.14),
            0.08,
            0.99,
        ),
        3,
    )
    ip_risk_score = round(
        _clamp(
            rng.gauss(0.22 + (0.35 if is_international else 0.08), 0.18),
            0.02,
            0.96,
        ),
        3,
    )

    if channel == "ecommerce":
        device_trust_score = round(_clamp(device_trust_score - rng.uniform(0, 0.12), 0.08, 0.99), 3)
        ip_risk_score = round(_clamp(ip_risk_score + rng.uniform(0, 0.15), 0.02, 0.96), 3)

    failed_login_count_24h = rng.choices([0, 1, 2, 3, 4, 5], weights=[72, 14, 7, 4, 2, 1], k=1)[0]
    velocity_24h_count = max(1, int(rng.gauss(3.2, 1.6)))
    velocity_24h_count = min(velocity_24h_count, 16)

    hour_of_day = int(_clamp(rng.gauss(14, 5.5), 0, 23))
    is_new_payee = 1 if rng.random() < 0.18 else 0
    distance_from_home_km = round(
        abs(rng.gauss(45 if not is_international else 420, 180 if not is_international else 900)),
        2,
    )
    distance_from_home_km = min(distance_from_home_km, 12000)

    auth_method = rng.choices(
        AUTH_METHODS,
        weights=[28, 24, 38, 10],
        k=1,
    )[0]
    if channel == "card_present":
        auth_method = rng.choice(["pin", "biometric"])
    if channel == "atm" and rng.random() < 0.12:
        auth_method = "none"

    return {
        "customer_id": profile.customer_id,
        "account_age_days": profile.account_age_days,
        "amount": amount,
        "currency": profile.currency,
        "merchant_id": f"MRC-{rng.randint(10000, 99999)}",
        "merchant_category": category,
        "merchant_risk_score": _merchant_risk_for_category(category, rng),
        "channel": channel,
        "transaction_type": rng.choices(
            TRANSACTION_TYPES,
            weights=[62, 8, 22, 8],
            k=1,
        )[0],
        "card_type": rng.choices(CARD_TYPES, weights=[55, 38, 7], k=1)[0],
        "country": country,
        "is_international": is_international,
        "device_trust_score": device_trust_score,
        "ip_risk_score": ip_risk_score,
        "auth_method": auth_method,
        "device_os": rng.choices(DEVICE_OS, weights=[34, 36, 24, 6], k=1)[0],
        "session_duration_minutes": max(1, int(rng.gauss(18, 12))),
        "failed_login_count_24h": failed_login_count_24h,
        "velocity_24h_count": velocity_24h_count,
        "days_since_last_transaction": max(0, int(rng.expovariate(1 / 4))),
        "prior_chargebacks": profile.prior_chargebacks if rng.random() > 0.08 else rng.randint(0, 2),
        "hour_of_day": hour_of_day,
        "is_new_payee": is_new_payee,
        "distance_from_home_km": distance_from_home_km,
        "avg_30d_amount": profile.avg_30d_amount,
        "account_balance_before": profile.account_balance_before,
    }


def _fraud_logit_core(row: dict[str, Any]) -> float:
    return fraud_risk_logit(row)


def _calibrate_fraud_intercept(rows: list[dict[str, Any]]) -> float:
    """Shift intercept so expected fraud probability matches TARGET_FRAUD_RATE."""
    low, high = -4.0, 4.0
    for _ in range(32):
        mid = (low + high) / 2
        expected_rate = sum(_sigmoid(_fraud_logit_core(row) + mid) for row in rows) / len(rows)
        if expected_rate > TARGET_FRAUD_RATE:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def _apply_overlap_variants(row: dict[str, Any], label: int, rng: random.Random) -> None:
    """Mimic real-world ambiguity: some fraud looks benign; some legit looks risky."""
    if label == 1 and rng.random() < FRAUD_CAMOUFLAGE_RATE:
        row["device_trust_score"] = round(_clamp(rng.uniform(0.55, 0.92), 0.08, 0.99), 3)
        row["ip_risk_score"] = round(_clamp(rng.uniform(0.08, 0.42), 0.02, 0.96), 3)
        if rng.random() < 0.5:
            row["amount"] = round(row["avg_30d_amount"] * rng.uniform(0.4, 1.6), 2)
    elif label == 0 and rng.random() < LEGIT_RISKY_DECOY_RATE:
        row["device_trust_score"] = round(_clamp(rng.uniform(0.12, 0.38), 0.08, 0.99), 3)
        row["ip_risk_score"] = round(_clamp(rng.uniform(0.55, 0.88), 0.02, 0.96), 3)
        row["velocity_24h_count"] = max(row["velocity_24h_count"], rng.randint(7, 12))
        row["failed_login_count_24h"] = max(row["failed_login_count_24h"], rng.randint(2, 4))


def _assign_label(row: dict[str, Any], intercept_adjust: float, rng: random.Random) -> int:
    logit = _fraud_logit_core(row) + intercept_adjust + rng.gauss(0, LABEL_LOGIT_NOISE_STD)
    return 1 if rng.random() < _sigmoid(logit) else 0


def build_transactions_with_meta(
    count: int = TOTAL_COUNT, seed: int = GENERATION_SEED
) -> tuple[list[dict[str, Any]], float]:
    rng = random.Random(seed)
    customer_count = max(120, count // 15)
    profiles = _build_customer_profiles(customer_count, rng)
    profile_list = list(profiles.values())

    draft_rows: list[dict[str, Any]] = []
    for index in range(count):
        profile = profile_list[index % len(profile_list)]
        row = _sample_transaction_features(profile, rng)
        row["transaction_id"] = f"TXN-{index + 1:06d}"
        draft_rows.append(row)

    intercept_adjust = _calibrate_fraud_intercept(draft_rows)

    rows: list[dict[str, Any]] = []
    for row in draft_rows:
        # Provisional label drives overlap variants; final label is drawn on mutated features
        # so observables and label_is_fraud stay aligned (fixes weak prior / model PR-AUC).
        provisional = _assign_label(row, intercept_adjust, rng)
        _apply_overlap_variants(row, provisional, rng)
        label = _assign_label(row, intercept_adjust, rng)
        if rng.random() < LABEL_NOISE_RATE:
            label = 1 - label
        row["label_is_fraud"] = label
        rows.append(row)
    return rows, intercept_adjust


def build_transactions(count: int = TOTAL_COUNT, seed: int = GENERATION_SEED) -> list[dict[str, Any]]:
    rows, _ = build_transactions_with_meta(count=count, seed=seed)
    return rows


def _stratified_take(
    fraud_rows: list[dict[str, Any]],
    legit_rows: list[dict[str, Any]],
    *,
    fraud_take: int,
    legit_take: int,
) -> list[dict[str, Any]]:
    return fraud_rows[:fraud_take] + legit_rows[:legit_take]


def split_train_val_test(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Stratified shuffle split so train/val/test share similar fraud rates."""
    rng = random.Random(GENERATION_SEED + 99)
    fraud_rows = [row for row in rows if row["label_is_fraud"] == 1]
    legit_rows = [row for row in rows if row["label_is_fraud"] == 0]
    rng.shuffle(fraud_rows)
    rng.shuffle(legit_rows)

    total = len(rows)
    fraud_rate = len(fraud_rows) / total

    test_fraud = min(len(fraud_rows), max(1, round(TEST_COUNT * fraud_rate)))
    test_legit = TEST_COUNT - test_fraud
    test = _stratified_take(fraud_rows, legit_rows, fraud_take=test_fraud, legit_take=test_legit)
    fraud_rows = fraud_rows[test_fraud:]
    legit_rows = legit_rows[test_legit:]

    pool_fraud = len(fraud_rows)
    pool_legit = len(legit_rows)
    pool_total = pool_fraud + pool_legit
    train_share = ML_TRAIN_COUNT / TRAIN_POOL_COUNT if TRAIN_POOL_COUNT else 0.8

    train_fraud = min(pool_fraud, max(1, round(pool_fraud * train_share)))
    train_legit = min(pool_legit, ML_TRAIN_COUNT - train_fraud)
    if train_fraud + train_legit < ML_TRAIN_COUNT and pool_legit > train_legit:
        train_legit = min(pool_legit, ML_TRAIN_COUNT - train_fraud)

    train = _stratified_take(fraud_rows, legit_rows, fraud_take=train_fraud, legit_take=train_legit)
    fraud_rows = fraud_rows[train_fraud:]
    legit_rows = legit_rows[train_legit:]

    val_fraud = len(fraud_rows)
    val_legit = min(len(legit_rows), ML_VAL_COUNT - val_fraud)
    val = _stratified_take(fraud_rows, legit_rows, fraud_take=val_fraud, legit_take=val_legit)

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def _write_split_xlsx(split: str, rows: list[dict[str, Any]]) -> str:
    split_dir = fraud_split_dir(split)
    split_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = fraud_xlsx_path(split)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"Fraud_{split}"[:31]
    sheet.append(HEADERS)
    for row in rows:
        sheet.append([row[header] for header in HEADERS])
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(max(len(str(cell.value or "")) for cell in column) + 2, 28)
    workbook.save(xlsx_path)
    return str(xlsx_path.resolve())


def write_artifacts() -> dict[str, str]:
    root = fraud_data_root()
    root.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        split_dir = fraud_split_dir(split)
        if split_dir.exists():
            for path in split_dir.iterdir():
                if path.is_file() and path.name != ".gitkeep":
                    path.unlink()

    all_rows, fraud_logit_intercept = build_transactions_with_meta()
    train_rows, val_rows, test_rows = split_train_val_test(all_rows)

    paths = {
        "train_xlsx": _write_split_xlsx("train", train_rows),
        "val_xlsx": _write_split_xlsx("val", val_rows),
        "test_xlsx": _write_split_xlsx("test", test_rows),
    }

    metadata = {
        "dataset": FILE_BASENAME,
        "generation_seed": GENERATION_SEED,
        "feature_count": len(HEADERS) - 1,
        "target_fraud_rate": TARGET_FRAUD_RATE,
        "fraud_logit_intercept": round(fraud_logit_intercept, 6),
        "label_noise_rate": LABEL_NOISE_RATE,
        "total_generated_rows": len(all_rows),
        "train_count": len(train_rows),
        "val_count": len(val_rows),
        "test_count": len(test_rows),
        "train_fraud_label_count": sum(row["label_is_fraud"] for row in train_rows),
        "val_fraud_label_count": sum(row["label_is_fraud"] for row in val_rows),
        "test_fraud_label_count": sum(row["label_is_fraud"] for row in test_rows),
        "columns": [column for column in HEADERS if column != "label_is_fraud"],
        "description": (
            "Synthetic card and transfer data with customer profiles, overlap variants, and "
            "probabilistic labels drawn on final observables (features align with label_is_fraud)."
        ),
        "leakage_controls": {
            "split": "stratified disjoint train/val/test by transaction_id",
            "train_fit": "AutoGluon model weights fit on train split",
            "val": "threshold + validation metrics only (never in model.fit)",
            "test": "evaluate_test only; never passed to model.fit",
        },
    }
    metadata_path = fraud_metadata_path()
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    from app.use_cases.fraud_detection.risk_prior import fraud_logit_intercept_adjust

    fraud_logit_intercept_adjust.cache_clear()
    paths["metadata"] = str(metadata_path.resolve())
    return paths
