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
from app.use_cases.market_intelligence.agents import run_market_intelligence_workflow
from app.use_cases.market_intelligence.raw_data import DATASET_KEY_MARKET_INPUTS, USE_CASE_SLUG
from app.use_cases.market_intelligence.schemas import MarketIntelligencePayload, MarketResearchRequest
from app.use_cases.market_intelligence.web_search_service import SearchClient
from app.utils.json_safe import sanitize_for_json

MARKET_DAILY_RESULT_TYPE = "market_intelligence_daily_brief"
MARKET_RESEARCH_RESULT_TYPE = "market_intelligence_research"
ProgressCallback = Callable[[int, str], None]


def _ensure_datasets_seeded(session: Session) -> None:
    row = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_MARKET_INPUTS,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Market Intelligence data is not seeded. Run npm run data:generate and npm run db:seed.",
        )


def _latest_processed_result(session: Session, result_type: str) -> ProcessedResult | None:
    return session.exec(
        select(ProcessedResult)
        .where(ProcessedResult.use_case_slug == USE_CASE_SLUG, ProcessedResult.result_type == result_type)
        .order_by(desc(ProcessedResult.created_at))
        .limit(1)
    ).first()


def get_market_intelligence_latest(session: Session) -> dict:
    latest_daily = _latest_processed_result(session, MARKET_DAILY_RESULT_TYPE)
    latest_research = _latest_processed_result(session, MARKET_RESEARCH_RESULT_TYPE)

    def bundle(result: ProcessedResult | None) -> dict | None:
        if result is None:
            return None
        run = session.get(ModelRun, result.run_id)
        if run is None or run.status != "completed":
            return None
        return {"run": run.model_dump(), "result": result.model_dump(), "payload": result.payload}

    return {
        "use_case_slug": USE_CASE_SLUG,
        "latest": bundle(latest_daily),
        "latest_research": bundle(latest_research),
    }


def _default_daily_request(*, startup: bool = False) -> MarketResearchRequest:
    settings = get_settings()
    return MarketResearchRequest(
        objective="Create a daily executive banking market intelligence brief for US banking leaders.",
        region="US",
        focus_areas=["rates", "deposits", "credit", "regulation", "payments", "fraud"],
        depth="standard",
        max_search_calls=settings.market_max_search_calls_startup if startup else settings.market_max_search_calls_user_run,
        use_live_web=True,
    )


def _create_market_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    settings = get_settings()
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="multi-agent-openai-web-search",
        provider_used="openai-web-search",
        model_name=settings.market_research_model,
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
    payload: MarketIntelligencePayload,
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
            "workflow": "Budget-controlled multi-agent market research workflow.",
            "citations": "Live web claims require visible source URLs; synthetic fallback claims use generated source URLs.",
            "safety": "Market research support only, not investment advice.",
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


def _run_market_task(
    run_id: str,
    *,
    request: MarketResearchRequest,
    result_type: str,
    actor: str,
    action: str,
    startup_progress_callback: ProgressCallback | None = None,
    search_client: SearchClient | None = None,
) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        try:
            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)
                if startup_progress_callback is not None:
                    startup_progress_callback(percent, stage)

            payload = run_market_intelligence_workflow(
                request,
                mode="research" if result_type == MARKET_RESEARCH_RESULT_TYPE else "daily_brief",
                search_client=search_client,
                progress_callback=on_progress,
            )
            _persist_payload(
                session,
                run=run,
                result_type=result_type,
                payload=payload,
                actor=actor,
                action=action,
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


def run_market_intelligence_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_market_run(session)
        run_id = run.id
    _run_market_task(
        run_id,
        request=_default_daily_request(startup=True),
        result_type=MARKET_DAILY_RESULT_TYPE,
        actor="System",
        action="market_intelligence_daily_brief_completed",
        startup_progress_callback=progress_callback,
    )
    return run_id


def start_market_intelligence_run(session: Session) -> dict:
    run = _create_market_run(session)
    enqueue_user_job(
        f"market-intelligence-{run.id}",
        lambda: _run_market_task(
            run.id,
            request=_default_daily_request(startup=False),
            result_type=MARKET_DAILY_RESULT_TYPE,
            actor="Local Analyst",
            action="market_intelligence_daily_brief_completed",
        ),
    )
    return {"run_id": run.id, "status": "running"}


def research_market_intelligence(session: Session, request: MarketResearchRequest) -> dict:
    settings = get_settings()
    _ensure_datasets_seeded(session)
    if request.depth == "deep":
        request = request.model_copy(update={"max_search_calls": min(request.max_search_calls, settings.market_max_search_calls_deep)})
    else:
        request = request.model_copy(update={"max_search_calls": min(request.max_search_calls, settings.market_max_search_calls_user_run)})
    if request.use_live_web and not settings.openai_api_key:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "OpenAI API key is required for live Market Intelligence research.",
                "setup_hint": "Set OPENAI_API_KEY or run the request with use_live_web=false for synthetic corpus fallback.",
            },
        )
    run = _create_market_run(session)
    try:
        payload = run_market_intelligence_workflow(request, mode="research")
        result = _persist_payload(
            session,
            run=run,
            result_type=MARKET_RESEARCH_RESULT_TYPE,
            payload=payload,
            actor="Local Analyst",
            action="market_intelligence_research_completed",
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


def get_market_run_progress(run_id: str, session: Session) -> dict:
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


def get_market_run_result(run_id: str, session: Session) -> dict:
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
