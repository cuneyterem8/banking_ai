from app.data_paths import PLANNED_USE_CASE_FOLDERS, get_data_dir
from app.use_cases.aml_monitoring.data_generation import write_artifacts as write_aml_monitoring_artifacts
from app.use_cases.credit_risk.data_generation import write_artifacts as write_credit_artifacts
from app.use_cases.document_ocr.data_generation import write_artifacts as write_document_ocr_artifacts
from app.use_cases.email_automation.data_generation import write_artifacts as write_email_automation_artifacts
from app.use_cases.fraud_detection.data_generation import write_artifacts as write_fraud_artifacts
from app.use_cases.kyc_kyb.data_generation import write_artifacts as write_kyc_kyb_artifacts
from app.use_cases.liquidity_forecast.data_generation import write_artifacts as write_liquidity_forecast_artifacts
from app.use_cases.market_intelligence.data_generation import write_artifacts as write_market_intelligence_artifacts
from app.use_cases.support_chatbot.data_generation import write_artifacts as write_support_chatbot_artifacts
from app.use_cases.workflow_orchestration.data_generation import write_artifacts as write_workflow_orchestration_artifacts


def ensure_placeholder_dirs() -> None:
    data_dir = get_data_dir()
    for folder in PLANNED_USE_CASE_FOLDERS:
        placeholder = data_dir / folder / ".gitkeep"
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        if not placeholder.exists():
            placeholder.touch()


def main() -> None:
    ensure_placeholder_dirs()
    paths = {
        "fraud_detection": write_fraud_artifacts(),
        "credit_risk": write_credit_artifacts(),
        "document_ocr": write_document_ocr_artifacts(),
        "support_chatbot": write_support_chatbot_artifacts(),
        "liquidity_forecast": write_liquidity_forecast_artifacts(),
        "aml_monitoring": write_aml_monitoring_artifacts(),
        "kyc_kyb": write_kyc_kyb_artifacts(),
        "email_automation": write_email_automation_artifacts(),
        "market_intelligence": write_market_intelligence_artifacts(),
        "workflow_orchestration": write_workflow_orchestration_artifacts(),
    }
    print("Generated synthetic raw artifacts:")
    for use_case, use_case_paths in paths.items():
        print(f"- {use_case}:")
        for key, value in use_case_paths.items():
            print(f"  - {key}: {value}")


if __name__ == "__main__":
    main()
