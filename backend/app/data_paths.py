from pathlib import Path

from app.config import get_settings

# Registry slug (API) -> data/ folder name (snake_case)
USE_CASE_DATA_FOLDERS: dict[str, str] = {
    "fraud-detection": "fraud_detection",
    "credit-risk": "credit_risk",
    "document-ocr": "document_ocr",
    "support-chatbot": "support_chatbot",
    "liquidity-forecast": "liquidity_forecast",
    "aml-monitoring": "aml_monitoring",
    "kyc-kyb": "kyc_kyb",
    "email-automation": "email_automation",
    "market-intelligence": "market_intelligence",
    "workflow-orchestration": "workflow_orchestration",
}

PLANNED_USE_CASE_FOLDERS = tuple(
    folder for slug, folder in USE_CASE_DATA_FOLDERS.items() if slug != "fraud-detection"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    settings = get_settings()
    data_dir = settings.data_dir
    if data_dir.is_absolute():
        return data_dir
    return (repo_root() / data_dir.name).resolve()


def get_use_case_data_dir(slug: str) -> Path:
    folder = USE_CASE_DATA_FOLDERS.get(slug)
    if folder is None:
        raise KeyError(f"Unknown use case slug: {slug}")
    return get_data_dir() / folder


def slug_from_data_folder(folder: str) -> str | None:
    for slug, name in USE_CASE_DATA_FOLDERS.items():
        if name == folder:
            return slug
    return None
