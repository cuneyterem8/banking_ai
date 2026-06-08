from pathlib import Path

import pandas as pd

from app.use_cases.credit_risk.data_generation import (
    credit_metadata_path,
    credit_xlsx_path,
    write_artifacts,
)
from app.use_cases.credit_risk.schemas import CreditApplication

USE_CASE_SLUG = "credit-risk"
DATASET_KEY_TRAIN = "train"
DATASET_KEY_VAL = "val"
DATASET_KEY_TEST = "test"


def ensure_raw_artifacts() -> None:
    required = [
        credit_xlsx_path("train"),
        credit_xlsx_path("val"),
        credit_xlsx_path("test"),
        credit_metadata_path(),
    ]
    if not all(path.exists() for path in required):
        write_artifacts()


def _load_from_xlsx(split: str) -> list[CreditApplication]:
    ensure_raw_artifacts()
    frame = pd.read_excel(credit_xlsx_path(split))
    return [CreditApplication(**record) for record in frame.to_dict(orient="records")]


def load_train_applications() -> list[CreditApplication]:
    return _load_from_xlsx("train")


def load_val_applications() -> list[CreditApplication]:
    return _load_from_xlsx("val")


def load_test_applications() -> list[CreditApplication]:
    return _load_from_xlsx("test")


def raw_artifact_paths() -> list[Path]:
    ensure_raw_artifacts()
    return [
        credit_xlsx_path("train"),
        credit_xlsx_path("val"),
        credit_xlsx_path("test"),
        credit_metadata_path(),
    ]
