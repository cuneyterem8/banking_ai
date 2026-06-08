from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import HTTPException
from sqlmodel import Session, desc, select

from app.config import get_settings
from app.db.models import AuditEvent, ModelRun, ProcessedResult, RawDataset
from app.db.session import engine
from app.services.ml_job_queue import enqueue_user_job
from app.services.run_progress import complete_run_progress, fail_run_progress, get_run_progress, set_run_progress
from app.use_cases.email_automation.llm_service import LLMClient, generate_email_draft
from app.use_cases.email_automation.raw_data import (
    DATASET_KEY_EMAIL_INPUTS,
    USE_CASE_SLUG,
    load_campaigns,
    load_customers,
    load_events,
    load_evaluation_cases,
    load_templates,
)
from app.use_cases.email_automation.rules import evaluate_compliance
from app.use_cases.email_automation.schemas import (
    CampaignRecord,
    CustomerEvent,
    CustomerProfile,
    EmailAutomationDraft,
    EmailAutomationPayload,
    EmailAutomationScore,
    EmailAutomationSummary,
    EmailDraftRequest,
    EmailGenerationCase,
)
from app.use_cases.email_automation.scoring import score_draft
from app.use_cases.email_automation.template_engine import render_email_case
from app.utils.json_safe import sanitize_for_json

EMAIL_AUTOMATION_EVAL_RESULT_TYPE = "email_automation_evaluation"
EMAIL_AUTOMATION_DRAFT_RESULT_TYPE = "email_automation_draft"
ProgressCallback = Callable[[int, str], None]


def _ensure_datasets_seeded(session: Session) -> None:
    row = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_EMAIL_INPUTS,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Email Automation data is not seeded. Run npm run data:generate and npm run db:seed.",
        )


def _latest_processed_result(session: Session, result_type: str) -> ProcessedResult | None:
    return session.exec(
        select(ProcessedResult)
        .where(ProcessedResult.use_case_slug == USE_CASE_SLUG, ProcessedResult.result_type == result_type)
        .order_by(desc(ProcessedResult.created_at))
        .limit(1)
    ).first()


def get_email_automation_latest(session: Session) -> dict:
    latest_eval = _latest_processed_result(session, EMAIL_AUTOMATION_EVAL_RESULT_TYPE)
    latest_draft = _latest_processed_result(session, EMAIL_AUTOMATION_DRAFT_RESULT_TYPE)

    def bundle(result: ProcessedResult | None) -> dict | None:
        if result is None:
            return None
        run = session.get(ModelRun, result.run_id)
        if run is None or run.status != "completed":
            return None
        return {"run": run.model_dump(), "result": result.model_dump(), "payload": result.payload}

    return {
        "use_case_slug": USE_CASE_SLUG,
        "latest": bundle(latest_eval),
        "latest_draft": bundle(latest_draft),
    }


def _provider_for_drafts(drafts: list[EmailAutomationDraft]) -> str:
    providers = {draft.provider_used for draft in drafts}
    if "local-ollama" in providers and "gpt-4o-fallback" in providers:
        return "mixed-local-gpt4o"
    if "gpt-4o-fallback" in providers:
        return "gpt-4o-fallback"
    if "local-ollama" in providers:
        return "local-ollama"
    if "fallback-unavailable" in providers:
        return "fallback-unavailable"
    return "template-baseline"


def _model_name_for_drafts(drafts: list[EmailAutomationDraft]) -> str:
    model_names = sorted({draft.model_name for draft in drafts if draft.model_name})
    return ", ".join(model_names) if model_names else "template_engine"


def _summary(
    *,
    mode: str,
    drafts: list[EmailAutomationDraft],
    scores: list[EmailAutomationScore],
    fallback_count: int,
    timeout_count: int,
    invalid_json_count: int,
    warnings: list[str],
) -> EmailAutomationSummary:
    approved = sum(1 for draft in drafts if draft.compliance_status == "Approved")
    needs_review = sum(1 for draft in drafts if draft.compliance_status == "Needs Review")
    rejected = sum(1 for draft in drafts if draft.compliance_status == "Rejected")
    return EmailAutomationSummary(
        mode=mode,
        draft_count=len(drafts),
        service_draft_count=sum(1 for draft in drafts if draft.communication_type == "service"),
        campaign_draft_count=sum(1 for draft in drafts if draft.communication_type == "campaign"),
        approved_count=approved,
        needs_review_count=needs_review,
        rejected_count=rejected,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        invalid_json_count=invalid_json_count,
        warning_count=sum(len(draft.warnings) + len(draft.validation_issues) for draft in drafts) + len(warnings),
        average_quality_score=round(sum(score.quality_score for score in scores) / len(scores), 4) if scores else 0,
        approval_rate=round(approved / len(drafts), 4) if drafts else 0,
        provider_used=_provider_for_drafts(drafts),
        model_name=_model_name_for_drafts(drafts),
    )


def run_email_cases(
    cases: list[EmailGenerationCase],
    *,
    mode: str = "evaluation",
    ollama_client: LLMClient | None = None,
    openai_client: LLMClient | None = None,
    progress_callback: ProgressCallback | None = None,
) -> EmailAutomationPayload:
    customers = load_customers()
    events = load_events()
    campaigns = load_campaigns()
    templates = load_templates()
    drafts: list[EmailAutomationDraft] = []
    all_findings = []
    scores: list[EmailAutomationScore] = []
    fallback_count = 0
    timeout_count = 0
    invalid_json_count = 0
    warnings: list[str] = []

    for index, case in enumerate(cases, start=1):
        if progress_callback:
            progress_callback(5 + int((index - 1) / max(len(cases), 1) * 80), f"drafting_{case.case_id.lower()}")
        baseline = render_email_case(case, customers=customers, events=events, campaigns=campaigns, templates=templates)
        generated = generate_email_draft(
            case=case,
            baseline=baseline,
            ollama_client=ollama_client,
            openai_client=openai_client,
        )
        checked_draft, findings = evaluate_compliance(generated.draft)
        draft_score = score_draft(checked_draft, findings)
        drafts.append(checked_draft)
        all_findings.extend(findings)
        scores.append(draft_score)
        fallback_count += generated.stats.fallback_count
        timeout_count += generated.stats.timeout_count
        invalid_json_count += generated.stats.invalid_json_count
        warnings.extend(generated.stats.warnings)

    if progress_callback:
        progress_callback(90, "saving_results")
    warnings = list(dict.fromkeys(warnings))
    summary = _summary(
        mode=mode,
        drafts=drafts,
        scores=scores,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        invalid_json_count=invalid_json_count,
        warnings=warnings,
    )
    return EmailAutomationPayload(
        mode=mode,
        summary=summary,
        drafts=drafts,
        compliance_findings=all_findings,
        scores=scores,
        warnings=warnings,
    )


def _create_email_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    settings = get_settings()
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="template-rules-ollama-gpt4o-fallback",
        provider_used="local-ollama",
        model_name=settings.ollama_model,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    set_run_progress(run.id, 0, "queued")
    return run


def _persist_payload(
    session: Session,
    *,
    run: ModelRun,
    result_type: str,
    payload: EmailAutomationPayload,
    actor: str,
    action: str,
) -> ProcessedResult:
    run.status = "completed"
    run.provider_used = payload.summary.provider_used
    run.model_name = payload.summary.model_name
    run.metrics = sanitize_for_json(payload.summary.model_dump())
    run.finished_at = datetime.utcnow()
    run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    session.add(run)
    result = ProcessedResult(
        run_id=run.id,
        use_case_slug=USE_CASE_SLUG,
        result_type=result_type,
        payload=sanitize_for_json(payload.model_dump()),
        explanation={
            "generation": "Template baseline plus Ollama Qwen first and GPT-4o fallback.",
            "compliance": "Deterministic policy checks are applied after generation.",
        },
    )
    session.add(result)
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            entity_type="model_run",
            entity_id=run.id,
            metadata_json=sanitize_for_json(payload.summary.model_dump()),
        )
    )
    session.commit()
    session.refresh(result)
    session.refresh(run)
    return result


def _run_evaluation_task(run_id: str, startup_progress_callback: ProgressCallback | None = None) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        try:
            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)
                if startup_progress_callback is not None:
                    startup_progress_callback(percent, stage)

            cases = load_evaluation_cases()
            payload = run_email_cases(cases, progress_callback=on_progress)
            _persist_payload(
                session,
                run=run,
                result_type=EMAIL_AUTOMATION_EVAL_RESULT_TYPE,
                payload=payload,
                actor="System",
                action="email_automation_evaluation_completed",
            )
            complete_run_progress(run_id)
            if startup_progress_callback is not None:
                startup_progress_callback(100, "done")
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")
            raise


def run_email_automation_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_email_run(session)
        run_id = run.id
    _run_evaluation_task(run_id, progress_callback)
    return run_id


def start_email_automation_run(session: Session) -> dict:
    run = _create_email_run(session)
    enqueue_user_job(f"email-automation-{run.id}", lambda: _run_evaluation_task(run.id))
    return {"run_id": run.id, "status": "running"}


def _draft_case_from_request(
    request: EmailDraftRequest,
    *,
    customers: list[CustomerProfile],
    events: list[CustomerEvent],
    campaigns: list[CampaignRecord],
) -> EmailGenerationCase:
    if request.customer_id not in {customer.customer_id for customer in customers}:
        raise HTTPException(status_code=404, detail="Synthetic customer not found.")
    if request.communication_type == "service":
        matches = [
            event
            for event in events
            if event.customer_id == request.customer_id and (request.event_type is None or event.event_type == request.event_type)
        ]
        if not matches:
            raise HTTPException(status_code=404, detail="No matching synthetic service event found.")
        event = matches[0]
        return EmailGenerationCase(
            case_id=f"EMAIL-DRAFT-{request.customer_id}",
            communication_type="service",
            customer_id=request.customer_id,
            event_id=event.event_id,
            event_type=event.event_type,
            template_key=f"service:{event.event_type}",
            custom_context=request.custom_context,
            expected_required_disclosures=["This service message is not a marketing offer."],
        )
    if request.communication_type == "campaign":
        if not request.campaign_id:
            raise HTTPException(status_code=400, detail="campaign_id is required for campaign drafts.")
        matches = [
            campaign
            for campaign in campaigns
            if campaign.customer_id == request.customer_id and campaign.campaign_id == request.campaign_id
        ]
        if not matches:
            raise HTTPException(status_code=404, detail="No matching synthetic campaign audience row found.")
        campaign = matches[0]
        return EmailGenerationCase(
            case_id=f"EMAIL-DRAFT-{request.customer_id}-{request.campaign_id}",
            communication_type="campaign",
            customer_id=request.customer_id,
            campaign_id=campaign.campaign_id,
            audience_id=campaign.audience_id,
            template_key=f"campaign:{campaign.campaign_type}",
            custom_context=request.custom_context,
            expected_required_disclosures=[campaign.required_disclosure],
        )
    raise HTTPException(status_code=400, detail="communication_type must be service or campaign.")


def draft_email(session: Session, request: EmailDraftRequest) -> dict:
    _ensure_datasets_seeded(session)
    run = _create_email_run(session)
    try:
        case = _draft_case_from_request(
            request,
            customers=load_customers(),
            events=load_events(),
            campaigns=load_campaigns(),
        )
        payload = run_email_cases([case], mode="draft")
        result = _persist_payload(
            session,
            run=run,
            result_type=EMAIL_AUTOMATION_DRAFT_RESULT_TYPE,
            payload=payload,
            actor="Local Analyst",
            action="email_automation_draft_completed",
        )
        complete_run_progress(run.id)
        return {"run": run.model_dump(), "result": result.model_dump(), "payload": payload.model_dump()}
    except HTTPException:
        run.status = "failed"
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        fail_run_progress(run.id, "failed")
        raise
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        fail_run_progress(run.id, "failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_email_run_progress(run_id: str, session: Session) -> dict:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != USE_CASE_SLUG:
        raise HTTPException(status_code=404, detail="Run not found.")
    progress = get_run_progress(run_id)
    if progress is None:
        if run.status == "completed":
            return {"run_id": run_id, "status": "completed", "progress_percent": 100, "stage": "done"}
        if run.status == "failed":
            return {"run_id": run_id, "status": "failed", "progress_percent": 0, "stage": "failed"}
        return {"run_id": run_id, "status": run.status, "progress_percent": 0, "stage": "unknown"}
    return {
        "run_id": run_id,
        "status": progress.status if progress.status != "running" else run.status,
        "progress_percent": progress.progress_percent,
        "stage": progress.stage,
    }


def get_email_run_result(run_id: str, session: Session) -> dict:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != USE_CASE_SLUG:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status == "running":
        raise HTTPException(status_code=202, detail="Run is still in progress.")
    result = session.exec(select(ProcessedResult).where(ProcessedResult.run_id == run_id)).first()
    if result is None and run.status == "failed":
        raise HTTPException(status_code=500, detail=run.error_message or "Run failed.")
    if result is None:
        raise HTTPException(status_code=404, detail="Run result not found.")
    return {"run": run.model_dump(), "result": result.model_dump()}
