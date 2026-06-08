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
from app.use_cases.support_chatbot.llm_service import LLMClient, answer_question
from app.use_cases.support_chatbot.raw_data import DATASET_KEY_KNOWLEDGE_BASE, USE_CASE_SLUG, load_evaluation_cases
from app.use_cases.support_chatbot.retrieval import (
    build_knowledge_chunks,
    citation_contains_required_text,
    retrieve_chunks,
    source_recall_for_answer,
)
from app.use_cases.support_chatbot.schemas import (
    SupportChatRequest,
    SupportChatbotAnswer,
    SupportChatbotPayload,
    SupportChatbotSummary,
    SupportEvaluationCase,
)
from app.utils.json_safe import sanitize_for_json

SUPPORT_EVAL_RESULT_TYPE = "support_chatbot_evaluation"
SUPPORT_CHAT_RESULT_TYPE = "support_chatbot_chat"
ProgressCallback = Callable[[int, str], None]


def _ensure_datasets_seeded(session: Session) -> None:
    row = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_KNOWLEDGE_BASE,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Support Chatbot data is not seeded. Run npm run data:generate and npm run db:seed.",
        )


def _latest_processed_result(session: Session, result_type: str) -> ProcessedResult | None:
    return session.exec(
        select(ProcessedResult)
        .where(
            ProcessedResult.use_case_slug == USE_CASE_SLUG,
            ProcessedResult.result_type == result_type,
        )
        .order_by(desc(ProcessedResult.created_at))
        .limit(1)
    ).first()


def get_support_chatbot_latest(session: Session) -> dict:
    latest_eval = _latest_processed_result(session, SUPPORT_EVAL_RESULT_TYPE)
    latest_chat = _latest_processed_result(session, SUPPORT_CHAT_RESULT_TYPE)

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
        "latest_chat": bundle(latest_chat),
    }


def _provider_for_answers(answers: list[SupportChatbotAnswer]) -> str:
    providers = {answer.provider_used for answer in answers}
    if "local-ollama" in providers and "gpt-4o-fallback" in providers:
        return "mixed-local-gpt4o"
    if "gpt-4o-fallback" in providers:
        return "gpt-4o-fallback"
    if "local-ollama" in providers:
        return "local-ollama"
    return "fallback-unavailable"


def _summary(
    *,
    answers: list[SupportChatbotAnswer],
    cases: list[SupportEvaluationCase],
    fallback_count: int,
    timeout_count: int,
    invalid_json_count: int,
) -> SupportChatbotSummary:
    expected_by_id = {case.question_id: case for case in cases}
    citation_scores: list[float] = []
    recall_scores: list[float] = []
    for answer in answers:
        case = expected_by_id.get(answer.question_id or "")
        if case is None:
            continue
        citation_scores.append(citation_contains_required_text(answer.sources, case.must_cite))
        recall_scores.append(source_recall_for_answer(answer.sources, case.expected_source_ids))
    answered = [answer for answer in answers if answer.answer_status == "answered"]
    warnings = sum(len(answer.warnings) + len(answer.missing_information) for answer in answers)
    return SupportChatbotSummary(
        question_count=len(answers),
        answered_count=len(answered),
        citation_accuracy=round(sum(citation_scores) / len(citation_scores), 4) if citation_scores else 0,
        source_recall=round(sum(recall_scores) / len(recall_scores), 4) if recall_scores else 0,
        average_confidence=round(sum(answer.confidence for answer in answers) / len(answers), 4) if answers else 0,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        invalid_json_count=invalid_json_count,
        escalation_count=sum(1 for answer in answers if answer.escalation_required),
        warning_count=warnings,
        provider_used=_provider_for_answers(answers),
    )


def run_support_questions(
    cases: list[SupportEvaluationCase],
    *,
    ollama_client: LLMClient | None = None,
    openai_client: LLMClient | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> SupportChatbotPayload:
    chunks = build_knowledge_chunks()
    answers: list[SupportChatbotAnswer] = []
    fallback_count = 0
    timeout_count = 0
    invalid_json_count = 0
    for index, case in enumerate(cases, start=1):
        if progress_callback:
            progress_callback(5 + int((index - 1) / max(len(cases), 1) * 80), f"answering_{case.question_id.lower()}")
        sources, _all_chunks, retrieval_confidence, _no_answer = retrieve_chunks(case.question, chunks=chunks)
        generated = answer_question(
            question=case.question,
            question_id=case.question_id,
            retrieved_sources=sources,
            retrieval_confidence=retrieval_confidence,
            ollama_client=ollama_client,
            openai_client=openai_client,
        )
        answers.append(generated.answer)
        fallback_count += generated.stats.fallback_count
        timeout_count += generated.stats.timeout_count
        invalid_json_count += generated.stats.invalid_json_count
    if progress_callback:
        progress_callback(90, "saving_results")
    summary = _summary(
        answers=answers,
        cases=cases,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        invalid_json_count=invalid_json_count,
    )
    return SupportChatbotPayload(summary=summary, answers=answers, retrieved_chunks=chunks)


def _run_evaluation_task(run_id: str, startup_progress_callback: ProgressCallback | None = None) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        started_at = datetime.utcnow()
        try:
            cases = load_evaluation_cases()

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)
                if startup_progress_callback is not None:
                    startup_progress_callback(percent, stage)

            payload = run_support_questions(cases, progress_callback=on_progress)
            summary = payload.summary
            run.status = "completed"
            run.provider_used = summary.provider_used
            run.model_name = "Qwen/Ollama + gpt-4o" if summary.provider_used == "mixed-local-gpt4o" else summary.provider_used
            run.metrics = sanitize_for_json(summary.model_dump())
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
            session.add(run)
            session.add(
                ProcessedResult(
                    run_id=run.id,
                    use_case_slug=USE_CASE_SLUG,
                    result_type=SUPPORT_EVAL_RESULT_TYPE,
                    payload=sanitize_for_json(payload.model_dump()),
                    explanation={
                        "retrieval": "BM25 lexical retrieval over deterministic synthetic support policy chunks.",
                        "generation": "Ollama Qwen first, GPT-4o fallback on timeout, invalid JSON, or local unavailability.",
                    },
                )
            )
            session.add(
                AuditEvent(
                    actor="Local Analyst",
                    action="support_chatbot_evaluation_completed",
                    entity_type="model_run",
                    entity_id=run.id,
                    metadata_json=sanitize_for_json(summary.model_dump()),
                )
            )
            session.commit()
            complete_run_progress(run_id)
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")


def _create_support_evaluation_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    settings = get_settings()
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="ollama-qwen-gpt4o-fallback",
        provider_used="local-ollama",
        model_name=settings.ollama_model,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    set_run_progress(run.id, 0, "queued")
    return run


def run_support_evaluation_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_support_evaluation_run(session)
        run_id = run.id
    _run_evaluation_task(run_id, progress_callback)
    return run_id


def start_support_evaluation_run(session: Session) -> dict:
    run = _create_support_evaluation_run(session)
    enqueue_user_job(f"support-chatbot-{run.id}", lambda: _run_evaluation_task(run.id))
    return {"run_id": run.id, "status": "running"}


def get_support_run_progress(run_id: str, session: Session) -> dict:
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


def get_support_run_result(run_id: str, session: Session) -> dict:
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


def chat_support_question(session: Session, request: SupportChatRequest) -> dict:
    _ensure_datasets_seeded(session)
    settings = get_settings()
    started_at = datetime.utcnow()
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="ollama-qwen-gpt4o-fallback",
        provider_used="local-ollama",
        model_name=settings.ollama_model,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    try:
        sources, chunks, retrieval_confidence, _no_answer = retrieve_chunks(request.question)
        generated = answer_question(
            question=request.question,
            question_id=None,
            retrieved_sources=sources,
            retrieval_confidence=retrieval_confidence,
        )
        summary = _summary(
            answers=[generated.answer],
            cases=[],
            fallback_count=generated.stats.fallback_count,
            timeout_count=generated.stats.timeout_count,
            invalid_json_count=generated.stats.invalid_json_count,
        )
        payload = SupportChatbotPayload(summary=summary, answers=[generated.answer], retrieved_chunks=chunks)
        run.status = "completed"
        run.provider_used = summary.provider_used
        run.model_name = generated.answer.model_name
        run.metrics = sanitize_for_json(summary.model_dump())
        run.finished_at = datetime.utcnow()
        run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
        session.add(run)
        result = ProcessedResult(
            run_id=run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=SUPPORT_CHAT_RESULT_TYPE,
            payload=sanitize_for_json(payload.model_dump()),
            explanation={"retrieval": "BM25 top-k support context for one interactive question."},
        )
        session.add(result)
        session.add(
            AuditEvent(
                actor="Local Analyst",
                action="support_chatbot_chat_completed",
                entity_type="model_run",
                entity_id=run.id,
                metadata_json=sanitize_for_json(summary.model_dump()),
            )
        )
        session.commit()
        session.refresh(result)
        session.refresh(run)
        return {"run": run.model_dump(), "result": result.model_dump(), "payload": payload.model_dump()}
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
        session.add(run)
        session.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
