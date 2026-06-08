from pathlib import Path

import pandas as pd

from app.use_cases.fraud_detection.data_generation import (
    fraud_metadata_path,
    fraud_xlsx_path,
    write_artifacts,
)
from app.use_cases.fraud_detection.schemas import FraudTransaction


USE_CASE_SLUG = "fraud-detection"
DATASET_KEY_TRAIN = "train"
DATASET_KEY_VAL = "val"
DATASET_KEY_TEST = "test"


def ensure_raw_artifacts() -> None:
    required = [
        fraud_xlsx_path("train"),
        fraud_xlsx_path("val"),
        fraud_xlsx_path("test"),
        fraud_metadata_path(),
    ]
    if not all(path.exists() for path in required):
        write_artifacts()


def _load_from_xlsx(split: str) -> list[FraudTransaction]:
    ensure_raw_artifacts()
    frame = pd.read_excel(fraud_xlsx_path(split))
    return [FraudTransaction(**record) for record in frame.to_dict(orient="records")]


def load_train_transactions() -> list[FraudTransaction]:
    return _load_from_xlsx("train")


def load_val_transactions() -> list[FraudTransaction]:
    return _load_from_xlsx("val")


def load_test_transactions() -> list[FraudTransaction]:
    return _load_from_xlsx("test")


def raw_artifact_paths() -> list[Path]:
    ensure_raw_artifacts()
    return [
        fraud_xlsx_path("train"),
        fraud_xlsx_path("val"),
        fraud_xlsx_path("test"),
        fraud_metadata_path(),
    ]
