from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import HTTPException
from sqlmodel import Session, desc, select

from app.db.models import AuditEvent, ModelRun, ProcessedResult, RawDataset
from app.db.session import engine
from app.services.ml_job_queue import enqueue_user_job
from app.services.run_progress import complete_run_progress, fail_run_progress, get_run_progress, set_run_progress
from app.use_cases.workflow_orchestration.decisioning import route_case
from app.use_cases.workflow_orchestration.dependency_loader import load_dependency_snapshots, snapshots_for_case
from app.use_cases.workflow_orchestration.llm_service import SummaryClient, generate_case_summary
from app.use_cases.workflow_orchestration.raw_data import (
    DATASET_KEY_WORKFLOW_CASES,
    USE_CASE_SLUG,
    load_cases_by_ids,
    load_heldout_case_ids,
    load_startup_case_ids,
    load_workflow_definitions,
)
from app.use_cases.workflow_orchestration.schemas import (
    WorkflowCase,
    WorkflowCaseSummary,
    WorkflowDefinition,
    WorkflowOrchestrationPayload,
    WorkflowOrchestrationRequest,
    WorkflowOrchestrationSummary,
    WorkflowStepResult,
)
from app.use_cases.workflow_orchestration.workflow_engine import execute_workflow_case
from app.utils.json_safe import sanitize_for_json

WORKFLOW_STARTUP_RESULT_TYPE = "workflow_orchestration_startup_evaluation"
WORKFLOW_CASE_RUN_RESULT_TYPE = "workflow_orchestration_case_run"
ProgressCallback = Callable[[int, str], None]


def _ensure_datasets_seeded(session: Session) -> None:
    row = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_WORKFLOW_CASES,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Workflow Orchestration data is not seeded. Run npm run data:generate and npm run db:seed.",
        )


def _latest_processed_result(session: Session, result_type: str) -> ProcessedResult | None:
    return session.exec(
        select(ProcessedResult)
        .where(ProcessedResult.use_case_slug == USE_CASE_SLUG, ProcessedResult.result_type == result_type)
        .order_by(desc(ProcessedResult.created_at))
        .limit(1)
    ).first()


def get_workflow_orchestration_latest(session: Session) -> dict:
    latest_startup = _latest_processed_result(session, WORKFLOW_STARTUP_RESULT_TYPE)
    latest_case_run = _latest_processed_result(session, WORKFLOW_CASE_RUN_RESULT_TYPE)

    def bundle(result: ProcessedResult | None) -> dict | None:
        if result is None:
            return None
        run = session.get(ModelRun, result.run_id)
        if run is None or run.status != "completed":
            return None
        return {"run": run.model_dump(), "result": result.model_dump(), "payload": result.payload}

    return {
        "use_case_slug": USE_CASE_SLUG,
        "latest": bundle(latest_startup),
        "latest_case_run": bundle(latest_case_run),
    }


def _provider_for_summaries(summaries: list[WorkflowCaseSummary]) -> str:
    providers = {summary.provider_used for summary in summaries}
    if "local-ollama" in providers and "gpt-4o-fallback" in providers:
        return "local-orchestrator+mixed-local-gpt4o"
    if "gpt-4o-fallback" in providers:
        return "local-orchestrator+gpt-4o-fallback"
    if "local-ollama" in providers:
        return "local-orchestrator+local-ollama"
    return "local-orchestrator"


def _model_name_for_summaries(summaries: list[WorkflowCaseSummary]) -> str:
    model_names = sorted({summary.model_name for summary in summaries if summary.model_name})
    suffix = f" + {', '.join(model_names)}" if model_names else ""
    return f"deterministic-dag-orchestrator{suffix}"


def _summary(
    *,
    mode: str,
    cases,
    dependency_snapshots,
    sla_results,
    case_summaries: list[WorkflowCaseSummary],
    fallback_count: int,
    timeout_count: int,
    invalid_json_count: int,
    warnings: list[str],
) -> WorkflowOrchestrationSummary:
    status_counts: dict[str, int] = {}
    for case in cases:
        status_counts[case.final_status] = status_counts.get(case.final_status, 0) + 1
    raw_scores = [float(case.input_context.get("risk_score", 0)) for case in cases]
    average_risk = round(sum(raw_scores) / len(raw_scores), 4) if raw_scores else 0
    dependency_warnings = [item for item in dependency_snapshots if item.status != "available" or item.warning]
    return WorkflowOrchestrationSummary(
        mode=mode,
        case_count=len(cases),
        workflow_type_count=len({case.workflow_type for case in cases}),
        straight_through_count=status_counts.get("Straight Through Approved", 0),
        needs_review_count=status_counts.get("Needs Review", 0),
        escalated_count=status_counts.get("Escalated", 0),
        blocked_count=status_counts.get("Blocked", 0),
        rejected_count=status_counts.get("Rejected", 0),
        dependency_ready_count=sum(1 for item in dependency_snapshots if item.status == "available"),
        dependency_warning_count=len(dependency_warnings),
        sla_breach_count=sum(1 for item in sla_results if item.sla_status == "Breached"),
        average_risk_score=average_risk,
        summary_count=len(case_summaries),
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        invalid_json_count=invalid_json_count,
        warning_count=len(warnings) + sum(len(summary.warnings) for summary in case_summaries),
        provider_used=_provider_for_summaries(case_summaries),
        model_name=_model_name_for_summaries(case_summaries),
    )


def _definition_by_type() -> dict[str, WorkflowDefinition]:
    return {definition.workflow_type: definition for definition in load_workflow_definitions()}


def run_workflow_cases(
    session: Session,
    cases: list[WorkflowCase],
    *,
    mode: str = "startup_evaluation",
    include_llm_summary: bool = True,
    ollama_client: SummaryClient | None = None,
    openai_client: SummaryClient | None = None,
    progress_callback: ProgressCallback | None = None,
) -> WorkflowOrchestrationPayload:
    definitions = _definition_by_type()
    dependency_snapshots = load_dependency_snapshots(session)
    case_results = []
    workflow_steps: list[WorkflowStepResult] = []
    routing_decisions = []
    sla_results = []
    case_summaries: list[WorkflowCaseSummary] = []
    fallback_count = 0
    timeout_count = 0
    invalid_json_count = 0
    warnings: list[str] = [item.warning for item in dependency_snapshots if item.warning]

    for index, case in enumerate(cases, start=1):
        if progress_callback:
            progress_callback(6 + int((index - 1) / max(len(cases), 1) * 78), f"orchestrating_{case.case_id}")
        definition = definitions[case.workflow_type]
        case_dependencies = snapshots_for_case(case.dependency_slugs, dependency_snapshots)
        steps = execute_workflow_case(case, definition, case_dependencies)
        case_result, routing, sla = route_case(case, steps, case_dependencies)
        case_results.append(case_result)
        workflow_steps.extend(steps)
        routing_decisions.append(routing)
        sla_results.append(sla)
        if include_llm_summary:
            generated = generate_case_summary(
                case_result=case_result,
                steps=steps,
                routing=routing,
                ollama_client=ollama_client,
                openai_client=openai_client,
            )
            case_summaries.append(generated.summary)
            fallback_count += generated.stats.fallback_count
            timeout_count += generated.stats.timeout_count
            invalid_json_count += generated.stats.invalid_json_count
            warnings.extend(generated.stats.warnings)

    if progress_callback:
        progress_callback(90, "saving_results")
    warnings = list(dict.fromkeys(warning for warning in warnings if warning))
    summary = _summary(
        mode=mode,
        cases=case_results,
        dependency_snapshots=dependency_snapshots,
        sla_results=sla_results,
        case_summaries=case_summaries,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        invalid_json_count=invalid_json_count,
        warnings=warnings,
    )
    return WorkflowOrchestrationPayload(
        mode=mode,
        summary=summary,
        cases=case_results,
        workflow_steps=workflow_steps,
        dependency_snapshots=dependency_snapshots,
        routing_decisions=routing_decisions,
        case_summaries=case_summaries,
        sla_results=sla_results,
        warnings=warnings,
    )


def _create_workflow_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="deterministic-dag-orchestrator-ollama-gpt4o-fallback",
        provider_used="local-orchestrator",
        model_name="deterministic-dag-orchestrator",
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
    payload: WorkflowOrchestrationPayload,
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
            "orchestration": "Deterministic workflow DAG execution over synthetic cases.",
            "dependencies": "Reads latest persisted outputs from the first nine use cases without retraining or rerunning them.",
            "llm": "LLM summaries are explanatory only; deterministic decision rules are authoritative.",
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


def _run_workflow_task(
    run_id: str,
    *,
    case_ids: list[str],
    result_type: str,
    mode: str,
    actor: str,
    action: str,
    include_llm_summary: bool = True,
    startup_progress_callback: ProgressCallback | None = None,
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

            cases = load_cases_by_ids(case_ids)
            payload = run_workflow_cases(
                session,
                cases,
                mode=mode,
                include_llm_summary=include_llm_summary,
                progress_callback=on_progress,
            )
            _persist_payload(session, run=run, result_type=result_type, payload=payload, actor=actor, action=action)
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


def run_workflow_orchestration_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_workflow_run(session)
        run_id = run.id
    _run_workflow_task(
        run_id,
        case_ids=load_startup_case_ids(),
        result_type=WORKFLOW_STARTUP_RESULT_TYPE,
        mode="startup_evaluation",
        actor="System",
        action="workflow_orchestration_startup_completed",
        startup_progress_callback=progress_callback,
    )
    return run_id


def start_workflow_orchestration_run(session: Session) -> dict:
    run = _create_workflow_run(session)
    enqueue_user_job(
        f"workflow-orchestration-{run.id}",
        lambda: _run_workflow_task(
            run.id,
            case_ids=load_heldout_case_ids(),
            result_type=WORKFLOW_CASE_RUN_RESULT_TYPE,
            mode="case_run",
            actor="Local Analyst",
            action="workflow_orchestration_case_run_completed",
        ),
    )
    return {"run_id": run.id, "status": "running"}


def orchestrate_workflow_case(session: Session, request: WorkflowOrchestrationRequest) -> dict:
    _ensure_datasets_seeded(session)
    run = _create_workflow_run(session)
    try:
        cases = load_cases_by_ids([request.case_id])
        if not cases:
            raise HTTPException(status_code=404, detail="Synthetic workflow case not found.")
        payload = run_workflow_cases(
            session,
            cases,
            mode="case_run",
            include_llm_summary=request.include_llm_summary,
        )
        result = _persist_payload(
            session,
            run=run,
            result_type=WORKFLOW_CASE_RUN_RESULT_TYPE,
            payload=payload,
            actor="Local Analyst",
            action="workflow_orchestration_selected_case_completed",
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


def get_workflow_run_progress(run_id: str, session: Session) -> dict:
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


def get_workflow_run_result(run_id: str, session: Session) -> dict:
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
