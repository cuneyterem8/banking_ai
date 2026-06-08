from __future__ import annotations

import os
import threading
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.ai.autogluon_adapter import AutoGluonTabularAdapter
from app.config import get_settings
from app.db.models import AuditEvent, ModelArtifact, ModelRun, ProcessedResult
from app.db.session import engine
from app.services.ml_job_queue import (
    enqueue_startup_job,
    is_api_ready,
    mark_startup_pipeline_complete,
    reset_startup_pipeline_complete,
)
from app.services.run_cleanup import reset_credit_for_training, reset_fraud_for_training, reset_startup_outputs
from app.use_cases.aml_monitoring.raw_data import USE_CASE_SLUG as AML_USE_CASE_SLUG
from app.use_cases.aml_monitoring.service import run_aml_monitoring_startup
from app.use_cases.credit_risk.raw_data import (
    USE_CASE_SLUG as CREDIT_USE_CASE_SLUG,
    load_train_applications,
    load_val_applications,
)
from app.use_cases.credit_risk.schemas import SplitEvaluation as CreditSplitEvaluation
from app.use_cases.credit_risk.service import CREDIT_VAL_RESULT_TYPE
from app.use_cases.credit_risk.training import (
    evaluation_payload_for_db as credit_evaluation_payload_for_db,
    get_model_dir as get_credit_model_dir,
    train_and_validate as credit_train_and_validate,
)
from app.use_cases.document_ocr.raw_data import USE_CASE_SLUG as DOCUMENT_OCR_USE_CASE_SLUG
from app.use_cases.document_ocr.service import run_document_ocr_startup
from app.use_cases.email_automation.raw_data import USE_CASE_SLUG as EMAIL_USE_CASE_SLUG
from app.use_cases.email_automation.service import run_email_automation_startup
from app.use_cases.fraud_detection.raw_data import USE_CASE_SLUG, load_train_transactions, load_val_transactions
from app.use_cases.fraud_detection.schemas import SplitEvaluation
from app.use_cases.fraud_detection.service import FRAUD_VAL_RESULT_TYPE
from app.use_cases.fraud_detection.training import (
    evaluation_payload_for_db,
    get_model_dir,
    train_and_validate,
)
from app.use_cases.kyc_kyb.raw_data import USE_CASE_SLUG as KYC_KYB_USE_CASE_SLUG
from app.use_cases.kyc_kyb.service import run_kyc_kyb_startup
from app.use_cases.liquidity_forecast.raw_data import USE_CASE_SLUG as LIQUIDITY_USE_CASE_SLUG
from app.use_cases.liquidity_forecast.service import run_liquidity_forecast_startup
from app.use_cases.market_intelligence.raw_data import USE_CASE_SLUG as MARKET_USE_CASE_SLUG
from app.use_cases.market_intelligence.service import run_market_intelligence_startup
from app.use_cases.support_chatbot.raw_data import USE_CASE_SLUG as SUPPORT_USE_CASE_SLUG
from app.use_cases.support_chatbot.service import run_support_evaluation_startup
from app.utils.json_safe import sanitize_for_json

ProgressCallback = Callable[[int, str], None]
StageRunner = Callable[[ProgressCallback], str]

_TERMINAL_STATUSES = frozenset({"completed", "failed", "skipped"})
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartupStageDefinition:
    slug: str
    title: str
    order: int
    runner: StageRunner


@dataclass
class TrainingJobState:
    use_case_slug: str
    title: str
    order: int
    status: str = "idle"
    progress_percent: int = 0
    stage: str = "idle"
    training_run_id: str | None = None
    error: str | None = None


_lock = threading.Lock()


def _should_skip_training() -> bool:
    settings = get_settings()
    if settings.skip_startup_training or os.getenv("SKIP_STARTUP_TRAINING", "").lower() in {"1", "true", "yes"}:
        return True
    return False


def _evaluation_metrics(evaluation: SplitEvaluation) -> dict[str, Any]:
    return {
        "split": evaluation.split,
        "record_count": evaluation.record_count,
        "primary_metric": evaluation.primary_metric,
        "primary_metric_label": evaluation.primary_metric_label,
        "primary_score": evaluation.primary_score,
        "precision": evaluation.precision,
        "recall": evaluation.recall,
        "f1": evaluation.f1,
        "accuracy": evaluation.accuracy,
        "roc_auc": evaluation.roc_auc,
        "correct_predictions": evaluation.correct_predictions,
        "threshold": evaluation.threshold,
        "confusion_matrix": evaluation.confusion_matrix.model_dump(),
    }


def _credit_evaluation_metrics(evaluation: CreditSplitEvaluation) -> dict[str, Any]:
    return {
        "split": evaluation.split,
        "record_count": evaluation.record_count,
        "primary_metric": evaluation.primary_metric,
        "primary_metric_label": evaluation.primary_metric_label,
        "primary_score": evaluation.primary_score,
        "pr_auc": evaluation.pr_auc,
        "precision": evaluation.precision,
        "recall": evaluation.recall,
        "f1": evaluation.f1,
        "accuracy": evaluation.accuracy,
        "correct_predictions": evaluation.correct_predictions,
        "threshold": evaluation.threshold,
        "confusion_matrix": evaluation.confusion_matrix.model_dump(),
    }


def _persist_training_result(
    val_evaluation: SplitEvaluation,
    explanation: dict[str, Any],
    duration_ms: int,
) -> str:
    with Session(engine) as session:
        run = ModelRun(
            use_case_slug=USE_CASE_SLUG,
            adapter_type="autogluon-tabular",
            provider_used="local-autogluon",
            model_name="autogluon.tabular.TabularPredictor",
            status="completed",
            duration_ms=duration_ms,
            metrics=sanitize_for_json(_evaluation_metrics(val_evaluation)),
        )
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)

        session.add(
            ProcessedResult(
                run_id=run.id,
                use_case_slug=USE_CASE_SLUG,
                result_type=FRAUD_VAL_RESULT_TYPE,
                payload=evaluation_payload_for_db(val_evaluation),
                explanation=explanation,
            )
        )
        session.add(
            ModelArtifact(
                use_case_slug=USE_CASE_SLUG,
                artifact_type="autogluon_model_directory",
                local_path="storage/models/fraud-detection/autogluon",
                metadata_json={
                    "provider": "local-autogluon",
                    "preset": get_settings().autogluon_preset,
                    "trained_on": "train",
                    "threshold": "val",
                },
            )
        )
        session.add(
            AuditEvent(
                actor="System",
                action="fraud_training_completed",
                entity_type="model_run",
                entity_id=run.id,
                metadata_json={
                    "split": "val",
                    "primary_score": val_evaluation.primary_score,
                    "accuracy": val_evaluation.accuracy,
                },
            )
        )
        session.commit()
        return run.id


def _persist_credit_training_result(
    val_evaluation: CreditSplitEvaluation,
    explanation: dict[str, Any],
    duration_ms: int,
) -> str:
    with Session(engine) as session:
        run = ModelRun(
            use_case_slug=CREDIT_USE_CASE_SLUG,
            adapter_type="autogluon-tabular",
            provider_used="local-autogluon",
            model_name="autogluon.tabular.TabularPredictor",
            status="completed",
            duration_ms=duration_ms,
            metrics=sanitize_for_json(_credit_evaluation_metrics(val_evaluation)),
        )
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)

        session.add(
            ProcessedResult(
                run_id=run.id,
                use_case_slug=CREDIT_USE_CASE_SLUG,
                result_type=CREDIT_VAL_RESULT_TYPE,
                payload=credit_evaluation_payload_for_db(val_evaluation),
                explanation=explanation,
            )
        )
        session.add(
            ModelArtifact(
                use_case_slug=CREDIT_USE_CASE_SLUG,
                artifact_type="autogluon_model_directory",
                local_path="storage/models/credit-risk/autogluon",
                metadata_json={
                    "provider": "local-autogluon",
                    "primary_metric": "roc_auc",
                    "target": "label_default_12m",
                    "threshold": "val",
                },
            )
        )
        session.add(
            AuditEvent(
                actor="System",
                action="credit_training_completed",
                entity_type="model_run",
                entity_id=run.id,
                metadata_json={
                    "split": "val",
                    "primary_score": val_evaluation.primary_score,
                    "accuracy": val_evaluation.accuracy,
                },
            )
        )
        session.commit()
        return run.id


def _run_fraud_training(progress_callback: ProgressCallback) -> str:
    started = datetime.utcnow()
    progress_callback(2, "resetting")
    with Session(engine) as session:
        reset_fraud_for_training(session)
    AutoGluonTabularAdapter(artifact_dir=get_model_dir())._clear_model()

    progress_callback(8, "loading_data")
    train_rows = [item.model_dump() for item in load_train_transactions()]
    val_rows = [item.model_dump() for item in load_val_transactions()]
    _, val_evaluation, explanation = train_and_validate(
        train_rows,
        val_rows,
        progress_callback=progress_callback,
        force_retrain=True,
    )
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    return _persist_training_result(val_evaluation, explanation, duration_ms)


def _run_credit_training(progress_callback: ProgressCallback) -> str:
    started = datetime.utcnow()
    progress_callback(2, "resetting")
    with Session(engine) as session:
        reset_credit_for_training(session)
    AutoGluonTabularAdapter(artifact_dir=get_credit_model_dir())._clear_model()

    progress_callback(8, "loading_data")
    train_rows = [item.model_dump() for item in load_train_applications()]
    val_rows = [item.model_dump() for item in load_val_applications()]
    _, val_evaluation, explanation = credit_train_and_validate(
        train_rows,
        val_rows,
        progress_callback=progress_callback,
        force_retrain=True,
    )
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    return _persist_credit_training_result(val_evaluation, explanation, duration_ms)


STARTUP_STAGES: tuple[StartupStageDefinition, ...] = (
    StartupStageDefinition(USE_CASE_SLUG, "Fraud Detection", 1, _run_fraud_training),
    StartupStageDefinition(CREDIT_USE_CASE_SLUG, "Credit Risk", 2, _run_credit_training),
    StartupStageDefinition(DOCUMENT_OCR_USE_CASE_SLUG, "Document OCR", 3, run_document_ocr_startup),
    StartupStageDefinition(SUPPORT_USE_CASE_SLUG, "Support Chatbot", 4, run_support_evaluation_startup),
    StartupStageDefinition(LIQUIDITY_USE_CASE_SLUG, "Liquidity Forecast", 5, run_liquidity_forecast_startup),
    StartupStageDefinition(AML_USE_CASE_SLUG, "AML Monitoring", 6, run_aml_monitoring_startup),
    StartupStageDefinition(KYC_KYB_USE_CASE_SLUG, "KYC/KYB", 7, run_kyc_kyb_startup),
    StartupStageDefinition(EMAIL_USE_CASE_SLUG, "Email Automation", 8, run_email_automation_startup),
    StartupStageDefinition(MARKET_USE_CASE_SLUG, "Market Intelligence", 9, run_market_intelligence_startup),
)

_stage_by_slug = {stage.slug: stage for stage in STARTUP_STAGES}
_stage_states = {
    stage.slug: TrainingJobState(use_case_slug=stage.slug, title=stage.title, order=stage.order)
    for stage in STARTUP_STAGES
}

# Compatibility for existing tests and imports.
_state = _stage_states[USE_CASE_SLUG]
_credit_state = _stage_states[CREDIT_USE_CASE_SLUG]


def _state_payload(state: TrainingJobState) -> dict[str, Any]:
    return {
        "use_case_slug": state.use_case_slug,
        "title": state.title,
        "order": state.order,
        "status": state.status,
        "progress_percent": state.progress_percent,
        "stage": state.stage,
        "training_run_id": state.training_run_id,
        "error": state.error,
    }


def _set_state(
    slug: str,
    *,
    status: str | None = None,
    progress_percent: int | None = None,
    stage: str | None = None,
    training_run_id: str | None = None,
    error: str | None = None,
) -> None:
    with _lock:
        state = _stage_states[slug]
        if status is not None:
            state.status = status
        if progress_percent is not None:
            state.progress_percent = max(0, min(100, progress_percent))
        if stage is not None:
            state.stage = stage
        if training_run_id is not None:
            state.training_run_id = training_run_id
        state.error = error


def _progress_for(slug: str) -> ProgressCallback:
    def on_progress(percent: int, stage: str) -> None:
        _set_state(slug, status="running", progress_percent=percent, stage=stage)

    return on_progress


def get_training_status(slug: str = USE_CASE_SLUG) -> dict[str, Any]:
    with _lock:
        state = _stage_states.get(slug)
        if state is None:
            return {
                "use_case_slug": slug,
                "title": slug,
                "order": 0,
                "status": "skipped",
                "progress_percent": 0,
                "stage": "not_implemented",
                "training_run_id": None,
                "error": None,
            }
        return _state_payload(state)


def is_startup_stage_completed(slug: str) -> bool:
    with _lock:
        state = _stage_states.get(slug)
        return state is not None and state.status == "completed"


def implemented_startup_slugs() -> set[str]:
    return set(_stage_by_slug)


def _active_state(states: list[dict[str, Any]]) -> dict[str, Any] | None:
    for state in states:
        if state["status"] in {"running", "queued"}:
            return state
    return None


def _ml_phase(active: dict[str, Any] | None, all_done: bool, skip: bool) -> str:
    if skip:
        return "skipped"
    if all_done:
        return "ready"
    if active is None:
        return "startup_pending"
    slug = active["use_case_slug"]
    if slug == USE_CASE_SLUG:
        return "fraud_training"
    if slug == CREDIT_USE_CASE_SLUG:
        return "credit_training"
    return f"{slug.replace('-', '_')}_training"


def get_startup_status() -> dict[str, Any]:
    with _lock:
        stages = [_state_payload(_stage_states[stage.slug]) for stage in STARTUP_STAGES]
    skip = _should_skip_training()
    all_done = skip or all(stage["status"] in _TERMINAL_STATUSES for stage in stages)
    active = _active_state(stages)
    completed_count = sum(1 for stage in stages if stage["status"] in _TERMINAL_STATUSES)
    return {
        "ready": is_api_ready(),
        "ml_training_ready": all_done,
        "ml_phase": _ml_phase(active, all_done, skip),
        "skip_startup_training": skip,
        "active_stage": active,
        "completed_stage_count": completed_count,
        "total_stage_count": len(stages),
        "stages": stages,
    }


def get_platform_readiness() -> dict[str, Any]:
    status = get_startup_status()
    fraud = get_training_status(USE_CASE_SLUG)
    credit = get_training_status(CREDIT_USE_CASE_SLUG)
    return {
        **status,
        "fraud_training": fraud,
        "credit_training": credit,
    }


def _mark_skipped() -> None:
    with _lock:
        for state in _stage_states.values():
            state.status = "skipped"
            state.stage = "skipped"
            state.progress_percent = 0
            state.training_run_id = None
            state.error = None


def _initialize_pipeline_states() -> None:
    with _lock:
        for stage in STARTUP_STAGES:
            state = _stage_states[stage.slug]
            state.status = "queued" if stage.order == 1 else "idle"
            state.stage = "queued" if stage.order == 1 else "idle"
            state.progress_percent = 0
            state.training_run_id = None
            state.error = None


def _stage_run_status(run_id: str | None) -> str:
    if run_id is None:
        return "completed"
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return "failed"
        return run.status


def _execute_stage(stage: StartupStageDefinition) -> None:
    _set_state(stage.slug, status="running", progress_percent=0, stage="starting", error=None)
    try:
        run_id = stage.runner(_progress_for(stage.slug))
        run_status = _stage_run_status(run_id)
        if run_status != "completed":
            raise RuntimeError(f"{stage.title} startup run finished with status {run_status}.")
        _set_state(
            stage.slug,
            status="completed",
            progress_percent=100,
            stage="done",
            training_run_id=run_id,
            error=None,
        )
    except Exception as exc:
        _set_state(stage.slug, status="failed", progress_percent=0, stage="failed", error=str(exc))
        raise


def run_fraud_startup_training() -> None:
    _execute_stage(_stage_by_slug[USE_CASE_SLUG])


def run_credit_startup_training() -> None:
    _execute_stage(_stage_by_slug[CREDIT_USE_CASE_SLUG])


def _enqueue_single_stage(stage: StartupStageDefinition) -> None:
    with _lock:
        state = _stage_states[stage.slug]
        if state.status == "running":
            return
        state.status = "queued"
        state.stage = "queued"
        state.progress_percent = 0
        state.training_run_id = None
        state.error = None
    enqueue_startup_job(f"{stage.slug}-startup", lambda: _execute_stage(stage))


def start_fraud_training_background() -> None:
    _enqueue_single_stage(_stage_by_slug[USE_CASE_SLUG])


def start_credit_training_background() -> None:
    _enqueue_single_stage(_stage_by_slug[CREDIT_USE_CASE_SLUG])


def start_all_training_background() -> None:
    reset_startup_pipeline_complete()
    if _should_skip_training():
        mark_startup_pipeline_complete()
        _mark_skipped()
        return

    with Session(engine) as session:
        reset_startup_outputs(session)
    _initialize_pipeline_states()

    def orchestrate() -> None:
        try:
            for stage in STARTUP_STAGES:
                _set_state(stage.slug, status="queued", progress_percent=0, stage="queued", error=None)
                try:
                    _execute_stage(stage)
                except Exception:
                    logger.exception("Startup stage failed: %s", stage.slug)
        finally:
            mark_startup_pipeline_complete()

    enqueue_startup_job("startup-pipeline", orchestrate)


USE_CASE_TRAINING_STARTERS = {
    stage.slug: (lambda selected_stage=stage: _enqueue_single_stage(selected_stage))
    for stage in STARTUP_STAGES
}
