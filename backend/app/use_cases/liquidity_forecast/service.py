from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import HTTPException
from sqlmodel import Session, desc, select

from app.db.models import AuditEvent, ModelRun, ProcessedResult, RawDataset
from app.db.session import engine
from app.services.ml_job_queue import enqueue_user_job
from app.services.run_progress import complete_run_progress, fail_run_progress, get_run_progress, set_run_progress
from app.use_cases.liquidity_forecast.forecasting import run_liquidity_forecast
from app.use_cases.liquidity_forecast.raw_data import DATASET_KEY_CASH_TIMESERIES, USE_CASE_SLUG
from app.utils.json_safe import sanitize_for_json

LIQUIDITY_FORECAST_RESULT_TYPE = "liquidity_forecast"
ProgressCallback = Callable[[int, str], None]


def _ensure_datasets_seeded(session: Session) -> None:
    row = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_CASH_TIMESERIES,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Liquidity Forecast data is not seeded. Run npm run data:generate and npm run db:seed.",
        )


def _latest_processed_result(session: Session) -> ProcessedResult | None:
    return session.exec(
        select(ProcessedResult)
        .where(
            ProcessedResult.use_case_slug == USE_CASE_SLUG,
            ProcessedResult.result_type == LIQUIDITY_FORECAST_RESULT_TYPE,
        )
        .order_by(desc(ProcessedResult.created_at))
        .limit(1)
    ).first()


def get_liquidity_latest(session: Session) -> dict:
    result = _latest_processed_result(session)
    if result is None:
        return {"use_case_slug": USE_CASE_SLUG, "latest": None}
    run = session.get(ModelRun, result.run_id)
    if run is None or run.status != "completed":
        return {"use_case_slug": USE_CASE_SLUG, "latest": None}
    return {
        "use_case_slug": USE_CASE_SLUG,
        "latest": {
            "run": run.model_dump(),
            "result": result.model_dump(),
            "payload": result.payload,
        },
    }


def _run_forecast_task(run_id: str, startup_progress_callback: ProgressCallback | None = None) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        started_at = datetime.utcnow()
        try:
            set_run_progress(run_id, 1, "running_forecast")
            if startup_progress_callback is not None:
                startup_progress_callback(1, "running_forecast")

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)
                if startup_progress_callback is not None:
                    startup_progress_callback(percent, stage)

            payload = run_liquidity_forecast(progress_callback=on_progress)
            summary = payload.summary
            set_run_progress(run_id, 92, "saving_results")
            run.status = "completed"
            run.provider_used = summary.provider_used
            run.model_name = summary.model_name
            run.metrics = sanitize_for_json(summary.model_dump())
            run.finished_at = datetime.utcnow()
            run.duration_ms = int((run.finished_at - started_at).total_seconds() * 1000)
            session.add(run)
            session.add(
                ProcessedResult(
                    run_id=run.id,
                    use_case_slug=USE_CASE_SLUG,
                    result_type=LIQUIDITY_FORECAST_RESULT_TYPE,
                    payload=sanitize_for_json(payload.model_dump()),
                    explanation={
                        "forecast_method": "AutoGluon TimeSeries when available; otherwise deterministic seasonal day-of-week baseline.",
                        "synthetic_ground_truth": "Metrics compare forecast horizon output against deterministic generated holdout actuals.",
                    },
                )
            )
            session.add(
                AuditEvent(
                    actor="Local Analyst",
                    action="liquidity_forecast_completed",
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


def _create_liquidity_forecast_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-timeseries",
        provider_used="local-seasonal-baseline",
        model_name="seasonal_day_of_week_baseline",
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    set_run_progress(run.id, 0, "queued")
    return run


def run_liquidity_forecast_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_liquidity_forecast_run(session)
        run_id = run.id
    _run_forecast_task(run_id, progress_callback)
    return run_id


def start_liquidity_forecast_run(session: Session) -> dict:
    run = _create_liquidity_forecast_run(session)
    enqueue_user_job(f"liquidity-forecast-{run.id}", lambda: _run_forecast_task(run.id))
    return {"run_id": run.id, "status": "running"}


def get_liquidity_run_progress(run_id: str, session: Session) -> dict:
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


def get_liquidity_run_result(run_id: str, session: Session) -> dict:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != USE_CASE_SLUG:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status == "running":
        raise HTTPException(status_code=202, detail="Run is still in progress.")
    result = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.run_id == run_id,
            ProcessedResult.result_type == LIQUIDITY_FORECAST_RESULT_TYPE,
        )
    ).first()
    if result is None and run.status == "failed":
        raise HTTPException(status_code=500, detail=run.error_message or "Run failed.")
    if result is None:
        raise HTTPException(status_code=404, detail="Run result not found.")
    return {"run": run.model_dump(), "result": result.model_dump()}
