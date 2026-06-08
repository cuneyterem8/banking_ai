import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.data_paths import get_use_case_data_dir
from app.use_cases.credit_risk.risk_prior import credit_default_logit

USE_CASE_SLUG = "credit-risk"
FILE_BASENAME = "synthetic_credit_applications"
TRAIN_POOL_COUNT = 2400
ML_TRAIN_COUNT = 1920
ML_VAL_COUNT = 480
TEST_COUNT = 600
TOTAL_COUNT = TRAIN_POOL_COUNT + TEST_COUNT
GENERATION_SEED = 7819
TARGET_DEFAULT_RATE = 0.12
LABEL_NOISE_RATE = 0.006
LABEL_LOGIT_NOISE_STD = 0.16

HEADERS = [
    "application_id",
    "customer_id",
    "age",
    "employment_status",
    "employment_years",
    "monthly_income",
    "monthly_expenses",
    "existing_debt",
    "requested_loan_amount",
    "requested_term_months",
    "loan_purpose",
    "home_ownership",
    "credit_history_months",
    "prior_defaults",
    "delinquencies_12m",
    "credit_utilization",
    "savings_balance",
    "checking_balance",
    "num_open_accounts",
    "recent_credit_inquiries",
    "region",
    "channel",
    "collateral_value",
    "label_default_12m",
    "target_loss_given_default",
]

EMPLOYMENT_STATUSES = ["salaried", "self_employed", "contract", "unemployed", "retired"]
LOAN_PURPOSES = ["auto", "home_improvement", "personal", "debt_consolidation", "education", "small_business"]
HOME_OWNERSHIP = ["own", "mortgage", "rent", "family"]
REGIONS = ["North", "South", "West", "East", "Central"]
CHANNELS = ["branch", "mobile", "web", "partner"]


@dataclass(frozen=True)
class ApplicantProfile:
    customer_id: str
    age: int
    region: str
    employment_status: str
    employment_years: float
    monthly_income: float
    monthly_expenses: float
    home_ownership: str
    credit_history_months: int


def credit_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def credit_metadata_path() -> Path:
    return credit_data_root() / "metadata.json"


def credit_split_dir(split: str) -> Path:
    return credit_data_root() / "raw" / split


def credit_xlsx_path(split: str) -> Path:
    return credit_split_dir(split) / f"{FILE_BASENAME}.xlsx"


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _build_profiles(count: int, rng: random.Random) -> list[ApplicantProfile]:
    profiles: list[ApplicantProfile] = []
    for index in range(count):
        employment_status = rng.choices(
            EMPLOYMENT_STATUSES,
            weights=[58, 17, 12, 6, 7],
            k=1,
        )[0]
        if employment_status == "unemployed":
            income = rng.uniform(650, 1600)
            employment_years = rng.uniform(0, 0.5)
        elif employment_status == "retired":
            income = rng.uniform(1200, 4500)
            employment_years = rng.uniform(15, 35)
        elif employment_status == "self_employed":
            income = rng.lognormvariate(8.1, 0.45)
            employment_years = rng.uniform(0.5, 16)
        else:
            income = rng.lognormvariate(8.0, 0.38)
            employment_years = rng.uniform(0.1, 18)
        income = _clamp(income, 800, 18000)
        profiles.append(
            ApplicantProfile(
                customer_id=f"CUST-{5000 + index}",
                age=rng.randint(21, 72),
                region=rng.choice(REGIONS),
                employment_status=employment_status,
                employment_years=round(employment_years, 1),
                monthly_income=round(income, 2),
                monthly_expenses=round(income * rng.uniform(0.35, 0.86), 2),
                home_ownership=rng.choices(HOME_OWNERSHIP, weights=[20, 30, 38, 12], k=1)[0],
                credit_history_months=rng.randint(4, 360),
            )
        )
    return profiles


def _sample_application(profile: ApplicantProfile, rng: random.Random, index: int) -> dict[str, Any]:
    purpose = rng.choices(LOAN_PURPOSES, weights=[20, 16, 22, 18, 10, 14], k=1)[0]
    term = rng.choice([12, 18, 24, 36, 48, 60, 72])
    requested = profile.monthly_income * rng.uniform(3, 24)
    if purpose == "auto":
        requested *= rng.uniform(1.1, 1.8)
    elif purpose == "small_business":
        requested *= rng.uniform(1.4, 2.8)
    requested = round(_clamp(requested, 1200, 250000), 2)
    existing_debt = round(profile.monthly_income * 12 * rng.betavariate(1.7, 5.2), 2)
    utilization = round(_clamp(rng.betavariate(2.0, 3.5) + rng.uniform(-0.06, 0.08), 0.02, 1.35), 3)
    prior_defaults = rng.choices([0, 1, 2], weights=[90, 8, 2], k=1)[0]
    delinquencies = rng.choices([0, 1, 2, 3, 4, 5], weights=[64, 18, 9, 5, 3, 1], k=1)[0]
    inquiries = rng.choices([0, 1, 2, 3, 4, 5, 6], weights=[30, 25, 18, 12, 8, 5, 2], k=1)[0]
    collateral_multiplier = 0.0
    if purpose in {"auto", "home_improvement", "small_business"}:
        collateral_multiplier = rng.uniform(0.2, 1.25)
    if profile.home_ownership in {"own", "mortgage"} and rng.random() < 0.25:
        collateral_multiplier += rng.uniform(0.1, 0.45)
    return {
        "application_id": f"APP-{index + 1:06d}",
        "customer_id": profile.customer_id,
        "age": profile.age,
        "employment_status": profile.employment_status,
        "employment_years": profile.employment_years,
        "monthly_income": profile.monthly_income,
        "monthly_expenses": profile.monthly_expenses,
        "existing_debt": existing_debt,
        "requested_loan_amount": requested,
        "requested_term_months": term,
        "loan_purpose": purpose,
        "home_ownership": profile.home_ownership,
        "credit_history_months": profile.credit_history_months,
        "prior_defaults": prior_defaults,
        "delinquencies_12m": delinquencies,
        "credit_utilization": utilization,
        "savings_balance": round(profile.monthly_income * rng.uniform(0.0, 8.5), 2),
        "checking_balance": round(profile.monthly_income * rng.uniform(0.05, 2.0), 2),
        "num_open_accounts": rng.randint(1, 18),
        "recent_credit_inquiries": inquiries,
        "region": profile.region,
        "channel": rng.choices(CHANNELS, weights=[26, 30, 32, 12], k=1)[0],
        "collateral_value": round(requested * collateral_multiplier, 2),
    }


def _calibrate_default_intercept(rows: list[dict[str, Any]]) -> float:
    low, high = -4.0, 4.0
    for _ in range(36):
        mid = (low + high) / 2
        expected_rate = sum(_sigmoid(credit_default_logit(row, include_intercept=False) + mid) for row in rows) / len(rows)
        if expected_rate > TARGET_DEFAULT_RATE:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def _loss_given_default(row: dict[str, Any], label: int, rng: random.Random) -> float:
    coverage = float(row["collateral_value"]) / max(float(row["requested_loan_amount"]), 1.0)
    base = 0.58 - 0.22 * min(coverage, 1.5)
    base += 0.08 if row["loan_purpose"] in {"personal", "debt_consolidation"} else 0.0
    base += 0.04 if int(row["prior_defaults"]) > 0 else 0.0
    if label == 0:
        base *= 0.35
    return round(_clamp(base + rng.gauss(0, 0.06), 0.02, 0.95), 3)


def build_applications_with_meta(
    count: int = TOTAL_COUNT,
    seed: int = GENERATION_SEED,
) -> tuple[list[dict[str, Any]], float]:
    rng = random.Random(seed)
    profiles = _build_profiles(max(150, count // 8), rng)
    draft_rows = [_sample_application(profiles[index % len(profiles)], rng, index) for index in range(count)]
    intercept = _calibrate_default_intercept(draft_rows)

    rows: list[dict[str, Any]] = []
    for row in draft_rows:
        logit = credit_default_logit(row, include_intercept=False) + intercept + rng.gauss(0, LABEL_LOGIT_NOISE_STD)
        label = 1 if rng.random() < _sigmoid(logit) else 0
        if rng.random() < LABEL_NOISE_RATE:
            label = 1 - label
        row["label_default_12m"] = label
        row["target_loss_given_default"] = _loss_given_default(row, label, rng)
        rows.append(row)
    return rows, intercept


def build_applications(count: int = TOTAL_COUNT, seed: int = GENERATION_SEED) -> list[dict[str, Any]]:
    rows, _ = build_applications_with_meta(count=count, seed=seed)
    return rows


def _stratified_take(default_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]], *, default_take: int, current_take: int) -> list[dict[str, Any]]:
    return default_rows[:default_take] + current_rows[:current_take]


def split_train_val_test(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(GENERATION_SEED + 33)
    default_rows = [row for row in rows if row["label_default_12m"] == 1]
    current_rows = [row for row in rows if row["label_default_12m"] == 0]
    rng.shuffle(default_rows)
    rng.shuffle(current_rows)
    default_rate = len(default_rows) / len(rows)

    test_default = min(len(default_rows), max(1, round(TEST_COUNT * default_rate)))
    test_current = TEST_COUNT - test_default
    test = _stratified_take(default_rows, current_rows, default_take=test_default, current_take=test_current)
    default_rows = default_rows[test_default:]
    current_rows = current_rows[test_current:]

    pool_default = len(default_rows)
    pool_current = len(current_rows)
    train_share = ML_TRAIN_COUNT / TRAIN_POOL_COUNT
    train_default = min(pool_default, max(1, round(pool_default * train_share)))
    train_current = min(pool_current, ML_TRAIN_COUNT - train_default)
    train = _stratified_take(default_rows, current_rows, default_take=train_default, current_take=train_current)
    default_rows = default_rows[train_default:]
    current_rows = current_rows[train_current:]

    val_default = len(default_rows)
    val_current = min(len(current_rows), ML_VAL_COUNT - val_default)
    val = _stratified_take(default_rows, current_rows, default_take=val_default, current_take=val_current)

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def _write_split_xlsx(split: str, rows: list[dict[str, Any]]) -> str:
    split_dir = credit_split_dir(split)
    split_dir.mkdir(parents=True, exist_ok=True)
    for path in split_dir.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()
    xlsx_path = credit_xlsx_path(split)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"Credit_{split}"[:31]
    sheet.append(HEADERS)
    for row in rows:
        sheet.append([row[header] for header in HEADERS])
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(max(len(str(cell.value or "")) for cell in column) + 2, 28)
    workbook.save(xlsx_path)
    return str(xlsx_path.resolve())


def write_artifacts() -> dict[str, str]:
    root = credit_data_root()
    root.mkdir(parents=True, exist_ok=True)

    rows, default_logit_intercept = build_applications_with_meta()
    train_rows, val_rows, test_rows = split_train_val_test(rows)
    paths = {
        "train_xlsx": _write_split_xlsx("train", train_rows),
        "val_xlsx": _write_split_xlsx("val", val_rows),
        "test_xlsx": _write_split_xlsx("test", test_rows),
    }
    metadata = {
        "dataset": FILE_BASENAME,
        "generation_seed": GENERATION_SEED,
        "feature_count": len(HEADERS) - 2,
        "target_default_rate": TARGET_DEFAULT_RATE,
        "default_logit_intercept": round(default_logit_intercept, 6),
        "label_noise_rate": LABEL_NOISE_RATE,
        "total_generated_rows": len(rows),
        "train_count": len(train_rows),
        "val_count": len(val_rows),
        "test_count": len(test_rows),
        "train_default_label_count": sum(row["label_default_12m"] for row in train_rows),
        "val_default_label_count": sum(row["label_default_12m"] for row in val_rows),
        "test_default_label_count": sum(row["label_default_12m"] for row in test_rows),
        "columns": [column for column in HEADERS if column not in {"label_default_12m", "target_loss_given_default"}],
        "description": "Synthetic loan applications with applicant affordability, credit history, collateral, and probabilistic 12-month default labels.",
        "leakage_controls": {
            "split": "stratified disjoint train/val/test by application_id",
            "train_fit": "AutoGluon model weights fit on train split",
            "val": "threshold + validation metrics only",
            "test": "evaluate_test only; never passed to model.fit",
        },
    }
    metadata_path = credit_metadata_path()
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    from app.use_cases.credit_risk.risk_prior import credit_logit_intercept_adjust

    credit_logit_intercept_adjust.cache_clear()
    paths["metadata"] = str(metadata_path.resolve())
    return paths
