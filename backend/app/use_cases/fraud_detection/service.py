from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, desc, select

from app.ai.base import AIAdapterUnavailable
from app.db.models import AuditEvent, ModelRun, ProcessedResult, RawDataset
from app.db.session import engine
from app.services.ml_job_queue import enqueue_user_job
from app.services.run_progress import (
    complete_run_progress,
    fail_run_progress,
    get_run_progress,
    set_run_progress,
)
from app.use_cases.fraud_detection.raw_data import (
    DATASET_KEY_TEST,
    DATASET_KEY_TRAIN,
    DATASET_KEY_VAL,
    USE_CASE_SLUG,
    load_test_transactions,
)
from app.use_cases.fraud_detection.schemas import SplitEvaluation
from app.use_cases.fraud_detection.training import evaluate_test, evaluation_payload_for_db
from app.utils.json_safe import sanitize_for_json

FRAUD_VAL_RESULT_TYPE = "fraud_val_evaluation"
FRAUD_TEST_RESULT_TYPE = "fraud_test_evaluation"


def _evaluation_from_payload(payload: dict) -> dict | None:
    nested = payload.get("evaluation")
    if isinstance(nested, dict) and nested.get("split"):
        return nested
    if payload.get("split") and payload.get("records") is not None:
        return payload
    return None


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


def get_fraud_evaluations(session: Session) -> dict:
    """Latest validation and test evaluations persisted in processed_results."""
    val_result = _latest_processed_result(session, FRAUD_VAL_RESULT_TYPE)
    test_result = _latest_processed_result(session, FRAUD_TEST_RESULT_TYPE)

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
        }

    return {
        "use_case_slug": USE_CASE_SLUG,
        "val": _bundle(val_result),
        "test": _bundle(test_result),
    }


def _ensure_datasets_seeded(session: Session) -> None:
    for key in (DATASET_KEY_TRAIN, DATASET_KEY_VAL, DATASET_KEY_TEST):
        row = session.exec(
            select(RawDataset).where(
                RawDataset.use_case_slug == USE_CASE_SLUG,
                RawDataset.dataset_key == key,
            )
        ).first()
        if row is None:
            raise HTTPException(
                status_code=409,
                detail="Fraud Detection datasets are not seeded. Run npm run data:generate and npm run db:seed.",
            )


def _evaluation_metrics(evaluation: SplitEvaluation) -> dict:
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
        "high_risk_count": sum(1 for item in evaluation.records if item.risk_level == "High"),
        "review_count": sum(1 for item in evaluation.records if item.decision != "Approve"),
        "average_fraud_probability": round(
            sum(item.fraud_probability for item in evaluation.records) / len(evaluation.records),
            4,
        )
        if evaluation.records
        else 0.0,
        "confusion_matrix": evaluation.confusion_matrix.model_dump(),
    }


def _run_test_evaluation_task(run_id: str) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        started_at = datetime.utcnow()
        try:
            set_run_progress(run_id, 1, "running_evaluation")
            test_rows = [item.model_dump() for item in load_test_transactions()]

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)

            test_evaluation, explanation = evaluate_test(test_rows, progress_callback=on_progress)
            set_run_progress(run_id, 90, "saving_results")

            run.status = "completed"
            run.provider_used = "local-autogluon"
            run.model_name = "autogluon.tabular.TabularPredictor"
            run.metrics = sanitize_for_json(_evaluation_metrics(test_evaluation))
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
            session.add(run)

            result = ProcessedResult(
                run_id=run.id,
                use_case_slug=USE_CASE_SLUG,
                result_type=FRAUD_TEST_RESULT_TYPE,
                payload=evaluation_payload_for_db(test_evaluation),
                explanation=explanation,
            )
            session.add(result)
            session.add(
                AuditEvent(
                    actor="Local Analyst",
                    action="fraud_detection_test_completed",
                    entity_type="model_run",
                    entity_id=run.id,
                    metadata_json={
                        "split": "test",
                        "primary_score": test_evaluation.primary_score,
                        "precision": test_evaluation.precision,
                        "recall": test_evaluation.recall,
                        "accuracy": test_evaluation.accuracy,
                        "roc_auc": test_evaluation.roc_auc,
                    },
                )
            )
            session.commit()
            complete_run_progress(run_id)
        except AIAdapterUnavailable as exc:
            run.status = "failed"
            run.error_message = exc.message
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
            run.metrics = {"setup_hint": exc.setup_hint}
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
            session.add(run)
            session.commit()
            fail_run_progress(run_id, "failed")


def start_fraud_test_run(session: Session) -> dict:
    _ensure_datasets_seeded(session)

    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    set_run_progress(run.id, 0, "queued")
    enqueue_user_job(f"fraud-test-{run.id}", lambda: _run_test_evaluation_task(run.id))
    return {"run_id": run.id, "status": "running"}


def get_fraud_run_progress(run_id: str, session: Session) -> dict:
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


def get_fraud_run_result(run_id: str, session: Session) -> dict:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != USE_CASE_SLUG:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status == "running":
        raise HTTPException(status_code=202, detail="Run is still in progress.")

    result = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.run_id == run_id,
            ProcessedResult.result_type == FRAUD_TEST_RESULT_TYPE,
        )
    ).first()
    if result is None and run.status == "failed":
        raise HTTPException(status_code=500, detail=run.error_message or "Run failed.")
    if result is None:
        raise HTTPException(status_code=404, detail="Run result not found.")

    return {"run": run.model_dump(), "result": result.model_dump()}
