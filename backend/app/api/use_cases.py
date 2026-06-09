from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, col, desc, select

from app.db.models import ModelRun, ProcessedResult, RawArtifact, RawDataset, UseCase
from app.db.session import get_session
from app.services.ml_training_manager import (
    get_training_status,
    implemented_startup_slugs,
    is_startup_stage_completed,
)
from app.use_cases.aml_monitoring.service import (
    get_aml_monitoring_latest,
    get_aml_run_progress,
    get_aml_run_result,
    start_aml_monitoring_run,
)
from app.use_cases.credit_risk.service import (
    get_credit_evaluations,
    get_credit_run_progress,
    get_credit_run_result,
    start_credit_test_run,
)
from app.use_cases.document_ocr.service import (
    get_document_ocr_latest,
    get_document_ocr_run_progress,
    get_document_ocr_run_result,
    start_document_ocr_run,
)
from app.use_cases.email_automation.schemas import EmailDraftRequest
from app.use_cases.email_automation.service import (
    draft_email,
    get_email_automation_latest,
    get_email_run_progress,
    get_email_run_result,
    start_email_automation_run,
)
from app.use_cases.fraud_detection.service import (
    get_fraud_evaluations,
    get_fraud_run_progress,
    get_fraud_run_result,
    start_fraud_test_run,
)
from app.use_cases.kyc_kyb.service import (
    get_kyc_kyb_latest,
    get_kyc_kyb_run_progress,
    get_kyc_kyb_run_result,
    start_kyc_kyb_run,
)
from app.use_cases.liquidity_forecast.service import (
    get_liquidity_latest,
    get_liquidity_run_progress,
    get_liquidity_run_result,
    start_liquidity_forecast_run,
)
from app.use_cases.market_intelligence.schemas import MarketResearchRequest
from app.use_cases.market_intelligence.service import (
    get_market_intelligence_latest,
    get_market_run_progress,
    get_market_run_result,
    research_market_intelligence,
    start_market_intelligence_run,
)
from app.use_cases.registry import get_use_case
from app.use_cases.support_chatbot.schemas import SupportChatRequest
from app.use_cases.support_chatbot.service import (
    chat_support_question,
    get_support_chatbot_latest,
    get_support_run_progress,
    get_support_run_result,
    start_support_evaluation_run,
)
from app.use_cases.workflow_orchestration.schemas import WorkflowOrchestrationRequest
from app.use_cases.workflow_orchestration.service import (
    get_workflow_orchestration_latest,
    get_workflow_run_progress,
    get_workflow_run_result,
    orchestrate_workflow_case,
    start_workflow_orchestration_run,
)

router = APIRouter(prefix="/use-cases", tags=["use-cases"])


@router.get("")
def list_use_cases(session: Session = Depends(get_session)) -> dict:
    rows = session.exec(select(UseCase).order_by(UseCase.implementation_order)).all()
    response = []
    for row in rows:
        latest_run = session.exec(
            select(ModelRun)
            .where(ModelRun.use_case_slug == row.slug)
            .order_by(desc(ModelRun.started_at))
            .limit(1)
        ).first()
        artifact_count = len(session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == row.slug)).all())
        result_count = len(session.exec(select(ProcessedResult).where(ProcessedResult.use_case_slug == row.slug)).all())
        response.append(
            {
                **row.model_dump(),
                "latest_run": latest_run.model_dump() if latest_run else None,
                "artifact_count": artifact_count,
                "result_count": result_count,
            }
        )
    return {"items": response}


@router.get("/{slug}")
def get_use_case_detail(slug: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(UseCase, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    return row.model_dump()


@router.get("/{slug}/raw")
def get_raw_data(slug: str, session: Session = Depends(get_session)) -> dict:
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")

    datasets = session.exec(select(RawDataset).where(RawDataset.use_case_slug == slug)).all()
    artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == slug)).all()
    return {
        "use_case": definition.__dict__,
        "datasets": [item.model_dump() for item in datasets],
        "artifacts": [item.model_dump() for item in artifacts],
    }


@router.get("/{slug}/training-status")
def training_status(slug: str) -> dict:
    if slug not in implemented_startup_slugs():
        raise HTTPException(status_code=404, detail="Training status is only available for implemented use cases.")
    return get_training_status(slug)


@router.get("/{slug}/evaluations")
def fraud_evaluations(slug: str, session: Session = Depends(get_session)) -> dict:
    if slug == "support-chatbot":
        return get_support_chatbot_latest(session)
    if slug == "document-ocr":
        return get_document_ocr_latest(session)
    if slug == "liquidity-forecast":
        return get_liquidity_latest(session)
    if slug == "aml-monitoring":
        return get_aml_monitoring_latest(session)
    if slug == "kyc-kyb":
        return get_kyc_kyb_latest(session)
    if slug == "email-automation":
        return get_email_automation_latest(session)
    if slug == "market-intelligence":
        return get_market_intelligence_latest(session)
    if slug == "workflow-orchestration":
        return get_workflow_orchestration_latest(session)
    if slug == "credit-risk":
        return get_credit_evaluations(session)
    if slug != "fraud-detection":
        raise HTTPException(status_code=404, detail="Evaluations endpoint is only available for implemented ML use cases.")
    return get_fraud_evaluations(session)


@router.post("/{slug}/run")
def run_use_case(slug: str, session: Session = Depends(get_session)):
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    if slug in implemented_startup_slugs() and not is_startup_stage_completed(slug):
        raise HTTPException(
            status_code=409,
            detail=f"{definition.title} startup processing is not complete yet.",
        )
    if slug == "fraud-detection":
        return start_fraud_test_run(session)
    if slug == "credit-risk":
        return start_credit_test_run(session)
    if slug == "document-ocr":
        return start_document_ocr_run(session)
    if slug == "support-chatbot":
        return start_support_evaluation_run(session)
    if slug == "liquidity-forecast":
        return start_liquidity_forecast_run(session)
    if slug == "aml-monitoring":
        return start_aml_monitoring_run(session)
    if slug == "kyc-kyb":
        return start_kyc_kyb_run(session)
    if slug == "email-automation":
        return start_email_automation_run(session)
    if slug == "market-intelligence":
        return start_market_intelligence_run(session)
    if slug == "workflow-orchestration":
        return start_workflow_orchestration_run(session)
    raise HTTPException(status_code=501, detail=f"{definition.title} is planned for a later staged implementation.")


@router.post("/{slug}/chat")
def chat_use_case(slug: str, request: SupportChatRequest, session: Session = Depends(get_session)) -> dict:
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    if slug != "support-chatbot":
        raise HTTPException(status_code=404, detail="Chat endpoint is only available for Support Chatbot.")
    return chat_support_question(session, request)


@router.post("/{slug}/draft")
def draft_use_case(slug: str, request: EmailDraftRequest, session: Session = Depends(get_session)) -> dict:
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    if slug != "email-automation":
        raise HTTPException(status_code=404, detail="Draft endpoint is only available for Email Automation.")
    if not is_startup_stage_completed(slug):
        raise HTTPException(
            status_code=409,
            detail=f"{definition.title} startup processing is not complete yet.",
        )
    return draft_email(session, request)


@router.post("/{slug}/research")
def research_use_case(slug: str, request: MarketResearchRequest, session: Session = Depends(get_session)) -> dict:
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    if slug != "market-intelligence":
        raise HTTPException(status_code=404, detail="Research endpoint is only available for Market Intelligence.")
    if not is_startup_stage_completed(slug):
        raise HTTPException(
            status_code=409,
            detail=f"{definition.title} startup processing is not complete yet.",
        )
    return research_market_intelligence(session, request)


@router.post("/{slug}/orchestrate")
def orchestrate_use_case(slug: str, request: WorkflowOrchestrationRequest, session: Session = Depends(get_session)) -> dict:
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    if slug != "workflow-orchestration":
        raise HTTPException(status_code=404, detail="Orchestrate endpoint is only available for Workflow Orchestration.")
    if not is_startup_stage_completed(slug):
        raise HTTPException(
            status_code=409,
            detail=f"{definition.title} startup processing is not complete yet.",
        )
    return orchestrate_workflow_case(session, request)


@router.get("/{slug}/runs/{run_id}/progress")
def run_progress(slug: str, run_id: str, session: Session = Depends(get_session)) -> dict:
    if slug == "support-chatbot":
        return get_support_run_progress(run_id, session)
    if slug == "document-ocr":
        return get_document_ocr_run_progress(run_id, session)
    if slug == "liquidity-forecast":
        return get_liquidity_run_progress(run_id, session)
    if slug == "aml-monitoring":
        return get_aml_run_progress(run_id, session)
    if slug == "kyc-kyb":
        return get_kyc_kyb_run_progress(run_id, session)
    if slug == "email-automation":
        return get_email_run_progress(run_id, session)
    if slug == "market-intelligence":
        return get_market_run_progress(run_id, session)
    if slug == "workflow-orchestration":
        return get_workflow_run_progress(run_id, session)
    if slug == "credit-risk":
        return get_credit_run_progress(run_id, session)
    if slug != "fraud-detection":
        raise HTTPException(status_code=404, detail="Run progress is only available for implemented ML use cases.")
    return get_fraud_run_progress(run_id, session)


@router.get("/{slug}/runs/{run_id}/result")
def run_result(slug: str, run_id: str, session: Session = Depends(get_session)) -> dict:
    if slug == "support-chatbot":
        return get_support_run_result(run_id, session)
    if slug == "document-ocr":
        return get_document_ocr_run_result(run_id, session)
    if slug == "liquidity-forecast":
        return get_liquidity_run_result(run_id, session)
    if slug == "aml-monitoring":
        return get_aml_run_result(run_id, session)
    if slug == "kyc-kyb":
        return get_kyc_kyb_run_result(run_id, session)
    if slug == "email-automation":
        return get_email_run_result(run_id, session)
    if slug == "market-intelligence":
        return get_market_run_result(run_id, session)
    if slug == "workflow-orchestration":
        return get_workflow_run_result(run_id, session)
    if slug == "credit-risk":
        return get_credit_run_result(run_id, session)
    if slug != "fraud-detection":
        raise HTTPException(status_code=404, detail="Run result endpoint is only available for implemented ML use cases.")
    return get_fraud_run_result(run_id, session)


@router.get("/{slug}/runs")
def list_runs(slug: str, session: Session = Depends(get_session)) -> dict:
    definition = get_use_case(slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Use case not found.")
    runs = session.exec(
        select(ModelRun).where(ModelRun.use_case_slug == slug).order_by(desc(ModelRun.started_at))
    ).all()
    return {"items": [item.model_dump() for item in runs]}


@router.get("/{slug}/runs/{run_id}")
def get_run(slug: str, run_id: str, session: Session = Depends(get_session)):
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != slug:
        raise HTTPException(status_code=404, detail="Run not found.")
    results = session.exec(select(ProcessedResult).where(col(ProcessedResult.run_id) == run_id)).all()
    if slug == "fraud-detection" and run.status == "running":
        return JSONResponse(
            status_code=202,
            content={
                "run": run.model_dump(),
                "results": [item.model_dump() for item in results],
                "message": "Run in progress. Poll /runs/{run_id}/progress.",
            },
        )
    return {
        "run": run.model_dump(),
        "results": [item.model_dump() for item in results],
    }
