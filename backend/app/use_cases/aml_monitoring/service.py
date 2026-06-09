from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import HTTPException
from sqlmodel import Session, desc, select

from app.ai.base import AIAdapterUnavailable
from app.db.models import AuditEvent, ModelArtifact, ModelRun, ProcessedResult, RawDataset
from app.db.session import engine
from app.services.ml_job_queue import enqueue_user_job
from app.services.run_progress import complete_run_progress, fail_run_progress, get_run_progress, set_run_progress
from app.use_cases.aml_monitoring.llm_service import NarrativeStats, draft_narratives_for_alerts
from app.use_cases.aml_monitoring.raw_data import (
    DATASET_KEY_TEST,
    DATASET_KEY_TRAIN,
    DATASET_KEY_VAL,
    USE_CASE_SLUG,
    case_note_summary,
    load_test_alerts,
    load_train_alerts,
    load_val_alerts,
    network_summary,
)
from app.use_cases.aml_monitoring.schemas import (
    AmlAlertDecision,
    AmlMonitoringSummary,
    AmlNarrativeDraft,
    AmlSplitEvaluation,
)
from app.use_cases.aml_monitoring.training import (
    evaluate_test,
    evaluation_payload_for_db,
    get_model_dir,
    train_and_validate,
)
from app.utils.json_safe import sanitize_for_json

AML_VAL_RESULT_TYPE = "aml_val_evaluation"
AML_TEST_RESULT_TYPE = "aml_test_evaluation"
NARRATIVE_LIMIT = 5
ProgressCallback = Callable[[int, str], None]


def _latest_processed_result(session: Session, result_type: str) -> ProcessedResult | None:
    return session.exec(
        select(ProcessedResult)
        .where(ProcessedResult.use_case_slug == USE_CASE_SLUG, ProcessedResult.result_type == result_type)
        .order_by(desc(ProcessedResult.created_at))
        .limit(1)
    ).first()


def _evaluation_from_payload(payload: dict) -> dict | None:
    nested = payload.get("evaluation")
    if isinstance(nested, dict) and nested.get("split"):
        return nested
    return None


def get_aml_monitoring_latest(session: Session) -> dict:
    val_result = _latest_processed_result(session, AML_VAL_RESULT_TYPE)
    test_result = _latest_processed_result(session, AML_TEST_RESULT_TYPE)

    def _bundle(result: ProcessedResult | None) -> dict | None:
        if result is None:
            return None
        run = session.get(ModelRun, result.run_id)
        if run is None or run.status != "completed":
            return None
        evaluation = _evaluation_from_payload(result.payload)
        if evaluation is None:
            return None
        return {
            "run": run.model_dump(),
            "result": result.model_dump(),
            "evaluation": evaluation,
            "payload": result.payload,
        }

    return {"use_case_slug": USE_CASE_SLUG, "val": _bundle(val_result), "test": _bundle(test_result)}


def _ensure_datasets_seeded(session: Session) -> None:
    for key in (DATASET_KEY_TRAIN, DATASET_KEY_VAL, DATASET_KEY_TEST):
        row = session.exec(
            select(RawDataset).where(RawDataset.use_case_slug == USE_CASE_SLUG, RawDataset.dataset_key == key)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=409,
                detail="AML Monitoring datasets are not seeded. Run npm run data:generate and npm run db:seed.",
            )


def _provider_used(narratives: list[AmlNarrativeDraft]) -> str:
    providers = {item.provider_used for item in narratives}
    if not providers:
        return "local-autogluon"
    if providers == {"fallback-unavailable"}:
        return "fallback-unavailable"
    if providers == {"local-ollama"}:
        return "local-autogluon+local-ollama"
    if providers == {"gpt-4o-fallback"}:
        return "local-autogluon+gpt-4o-fallback"
    return "local-autogluon+mixed-local-gpt4o"


def _model_name(narratives: list[AmlNarrativeDraft]) -> str:
    narrative_models = sorted({item.model_name for item in narratives if item.model_name != "none"})
    if not narrative_models:
        return "autogluon.tabular.TabularPredictor"
    return f"autogluon.tabular.TabularPredictor + {', '.join(narrative_models)}"


def _summary(
    *,
    evaluation: AmlSplitEvaluation,
    narratives: list[AmlNarrativeDraft],
    stats: NarrativeStats,
    warnings: list[str],
) -> AmlMonitoringSummary:
    alerts = evaluation.records
    return AmlMonitoringSummary(
        split=evaluation.split,
        alert_count=evaluation.record_count,
        sar_label_count=sum(item.actual_sar_recommended for item in alerts),
        high_risk_count=sum(1 for item in alerts if item.risk_level in {"High", "Critical"}),
        critical_risk_count=sum(1 for item in alerts if item.risk_level == "Critical"),
        narrative_count=len(narratives),
        fallback_count=stats.fallback_count,
        timeout_count=stats.timeout_count,
        invalid_json_count=stats.invalid_json_count,
        warning_count=len(warnings),
        average_sar_probability=round(sum(item.sar_probability for item in alerts) / len(alerts), 4) if alerts else 0,
        provider_used=_provider_used(narratives),
        model_name=_model_name(narratives),
        primary_score=evaluation.primary_score,
        precision=evaluation.precision,
        recall=evaluation.recall,
        f1=evaluation.f1,
        accuracy=evaluation.accuracy,
        roc_auc=evaluation.roc_auc,
        threshold=evaluation.threshold,
    )


def _evaluation_metrics(summary: AmlMonitoringSummary, evaluation: AmlSplitEvaluation) -> dict[str, Any]:
    return sanitize_for_json(
        {
            **summary.model_dump(),
            "primary_metric": evaluation.primary_metric,
            "primary_metric_label": evaluation.primary_metric_label,
            "confusion_matrix": evaluation.confusion_matrix.model_dump(),
        }
    )


def _persist_result(
    session: Session,
    *,
    run: ModelRun,
    result_type: str,
    evaluation: AmlSplitEvaluation,
    explanation: dict[str, Any],
    narratives: list[AmlNarrativeDraft],
    stats: NarrativeStats,
    warnings: list[str],
    audit_action: str,
    actor: str,
) -> None:
    network = network_summary()
    notes = case_note_summary()
    all_warnings = list(dict.fromkeys([*warnings, *stats.warnings]))
    summary = _summary(evaluation=evaluation, narratives=narratives, stats=stats, warnings=all_warnings)
    run.status = "completed"
    run.provider_used = summary.provider_used
    run.model_name = summary.model_name
    run.metrics = _evaluation_metrics(summary, evaluation)
    run.finished_at = datetime.utcnow()
    run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    session.add(run)
    session.add(
        ProcessedResult(
            run_id=run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=result_type,
            payload=evaluation_payload_for_db(
                evaluation,
                summary=summary.model_dump(),
                narratives=[item.model_dump() for item in narratives],
                network_summary=network.model_dump(),
                case_note_summary=notes.model_dump(),
                warnings=all_warnings,
            ),
            explanation=explanation,
        )
    )
    if result_type == AML_VAL_RESULT_TYPE:
        session.add(
            ModelArtifact(
                use_case_slug=USE_CASE_SLUG,
                artifact_type="autogluon_model_directory",
                local_path="models/aml-monitoring/autogluon",
                metadata_json={
                    "provider": "local-autogluon",
                    "primary_metric": "average_precision",
                    "target": "label_sar_recommended",
                    "threshold": "val",
                },
            )
        )
    session.add(
        AuditEvent(
            actor=actor,
            action=audit_action,
            entity_type="model_run",
            entity_id=run.id,
            metadata_json={
                "split": evaluation.split,
                "primary_score": evaluation.primary_score,
                "precision": evaluation.precision,
                "recall": evaluation.recall,
                "provider_used": summary.provider_used,
                "narrative_count": len(narratives),
            },
        )
    )
    session.commit()


def _create_aml_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular-local-llm-gpt4o-fallback",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    set_run_progress(run.id, 0, "queued")
    return run


def _run_validation_task(run_id: str, startup_progress_callback: ProgressCallback | None = None) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        try:
            set_run_progress(run_id, 1, "loading_aml_data")
            if startup_progress_callback:
                startup_progress_callback(1, "loading_aml_data")

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)
                if startup_progress_callback:
                    startup_progress_callback(percent, stage)

            train_rows = [item.model_dump() for item in load_train_alerts()]
            val_rows = [item.model_dump() for item in load_val_alerts()]
            _, val_evaluation, explanation = train_and_validate(
                train_rows,
                val_rows,
                progress_callback=on_progress,
                force_retrain=True,
            )
            on_progress(89, "drafting_validation_narratives")
            narratives, stats = draft_narratives_for_alerts(val_evaluation.records, limit=NARRATIVE_LIMIT)
            on_progress(94, "saving_results")
            _persist_result(
                session,
                run=run,
                result_type=AML_VAL_RESULT_TYPE,
                evaluation=val_evaluation,
                explanation=explanation,
                narratives=narratives,
                stats=stats,
                warnings=[],
                audit_action="aml_monitoring_validation_completed",
                actor="System",
            )
            complete_run_progress(run_id)
            if startup_progress_callback:
                startup_progress_callback(100, "done")
        except AIAdapterUnavailable as exc:
            run.status = "failed"
            run.error_message = exc.message
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            run.metrics = {"setup_hint": exc.setup_hint}
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")
            raise
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")
            raise


def _run_test_task(run_id: str) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        try:
            set_run_progress(run_id, 5, "loading_test_alerts")

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)

            test_rows = [item.model_dump() for item in load_test_alerts()]
            test_evaluation, explanation = evaluate_test(test_rows, progress_callback=on_progress)
            on_progress(72, "drafting_test_narratives")
            narratives, stats = draft_narratives_for_alerts(test_evaluation.records, limit=NARRATIVE_LIMIT)
            on_progress(93, "saving_results")
            _persist_result(
                session,
                run=run,
                result_type=AML_TEST_RESULT_TYPE,
                evaluation=test_evaluation,
                explanation=explanation,
                narratives=narratives,
                stats=stats,
                warnings=[],
                audit_action="aml_monitoring_test_completed",
                actor="Local Analyst",
            )
            complete_run_progress(run_id)
        except AIAdapterUnavailable as exc:
            run.status = "failed"
            run.error_message = exc.message
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            run.metrics = {"setup_hint": exc.setup_hint}
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")


def run_aml_monitoring_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_aml_run(session)
        run_id = run.id
    _run_validation_task(run_id, progress_callback)
    return run_id


def start_aml_monitoring_run(session: Session) -> dict:
    run = _create_aml_run(session)
    enqueue_user_job(f"aml-monitoring-test-{run.id}", lambda: _run_test_task(run.id))
    return {"run_id": run.id, "status": "running"}


def get_aml_run_progress(run_id: str, session: Session) -> dict:
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


def get_aml_run_result(run_id: str, session: Session) -> dict:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != USE_CASE_SLUG:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status == "running":
        raise HTTPException(status_code=202, detail="Run is still in progress.")
    result = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.run_id == run_id,
            ProcessedResult.result_type.in_((AML_VAL_RESULT_TYPE, AML_TEST_RESULT_TYPE)),
        )
    ).first()
    if result is None and run.status == "failed":
        raise HTTPException(status_code=500, detail=run.error_message or "Run failed.")
    if result is None:
        raise HTTPException(status_code=404, detail="Run result not found.")
    return {"run": run.model_dump(), "result": result.model_dump()}
