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
from app.use_cases.kyc_kyb.extraction import ExtractionStats, extract_packages
from app.use_cases.kyc_kyb.feature_engineering import build_feature_rows
from app.use_cases.kyc_kyb.raw_data import (
    DATASET_KEY_BUSINESS_PACKAGES,
    DATASET_KEY_INDIVIDUAL_PACKAGES,
    USE_CASE_SLUG,
    load_test_packages,
    load_train_packages,
    load_val_packages,
)
from app.use_cases.kyc_kyb.rules import evaluate_all_rules
from app.use_cases.kyc_kyb.schemas import (
    KycKybExtractedDocument,
    KycKybPackageRecord,
    KycKybRuleFinding,
    KycKybSplitEvaluation,
    KycKybSummary,
)
from app.use_cases.kyc_kyb.training import (
    evaluate_test,
    evaluation_payload_for_db,
    get_model_dir,
    train_and_validate,
)
from app.utils.json_safe import sanitize_for_json

KYC_KYB_VAL_RESULT_TYPE = "kyc_kyb_val_evaluation"
KYC_KYB_TEST_RESULT_TYPE = "kyc_kyb_test_evaluation"
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


def get_kyc_kyb_latest(session: Session) -> dict:
    val_result = _latest_processed_result(session, KYC_KYB_VAL_RESULT_TYPE)
    test_result = _latest_processed_result(session, KYC_KYB_TEST_RESULT_TYPE)

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
    for key in (DATASET_KEY_INDIVIDUAL_PACKAGES, DATASET_KEY_BUSINESS_PACKAGES):
        row = session.exec(
            select(RawDataset).where(RawDataset.use_case_slug == USE_CASE_SLUG, RawDataset.dataset_key == key)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=409,
                detail="KYC/KYB datasets are not seeded. Run npm run data:generate and npm run db:seed.",
            )


def _provider_used(documents: list[KycKybExtractedDocument]) -> str:
    providers = {item.provider_used for item in documents}
    if "fallback-unavailable" in providers:
        return "fallback-unavailable"
    if "gpt-4o-fallback" in providers:
        return "local-ocr-rules-autogluon+gpt-4o-fallback"
    return "local-ocr-rules-autogluon"


def _model_name(documents: list[KycKybExtractedDocument]) -> str:
    if any(item.provider_used == "gpt-4o-fallback" for item in documents):
        return "pdfplumber/PyMuPDF/openpyxl + autogluon.tabular.TabularPredictor + gpt-4o"
    return "pdfplumber/PyMuPDF/openpyxl + autogluon.tabular.TabularPredictor"


def _summary(
    *,
    packages: list[KycKybPackageRecord],
    documents: list[KycKybExtractedDocument],
    findings: list[KycKybRuleFinding],
    evaluation: KycKybSplitEvaluation,
    extraction_stats: ExtractionStats,
    warnings: list[str],
) -> KycKybSummary:
    decisions = evaluation.records
    hard_failed_packages = {
        item.package_id
        for item in findings
        if item.status == "failed" and (item.severity == "hard_fail" or item.rule_id.endswith("_match"))
    }
    return KycKybSummary(
        split=evaluation.split,
        package_count=len(packages),
        individual_count=sum(1 for item in packages if item.subject_type == "individual"),
        business_count=sum(1 for item in packages if item.subject_type == "business"),
        manual_review_label_count=sum(item.label_manual_review_required for item in packages),
        needs_review_count=sum(1 for item in decisions if item.verification_status == "Needs Review"),
        rejected_count=sum(1 for item in decisions if item.verification_status == "Rejected"),
        hard_rule_count=len(hard_failed_packages),
        extracted_document_count=len(documents),
        fallback_count=extraction_stats.fallback_count,
        warning_count=len(warnings),
        average_risk_score=round(sum(item.risk_score for item in decisions) / len(decisions), 4) if decisions else 0.0,
        provider_used=_provider_used(documents),
        model_name=_model_name(documents),
        primary_score=evaluation.primary_score,
        precision=evaluation.precision,
        recall=evaluation.recall,
        f1=evaluation.f1,
        accuracy=evaluation.accuracy,
        roc_auc=evaluation.roc_auc,
        threshold=evaluation.threshold,
    )


def _evaluation_metrics(summary: KycKybSummary, evaluation: KycKybSplitEvaluation) -> dict[str, Any]:
    return sanitize_for_json(
        {
            **summary.model_dump(),
            "primary_metric": evaluation.primary_metric,
            "primary_metric_label": evaluation.primary_metric_label,
            "confusion_matrix": evaluation.confusion_matrix.model_dump(),
        }
    )


def _prepare_rows(
    packages: list[KycKybPackageRecord],
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict[str, Any]], list[KycKybExtractedDocument], list[KycKybRuleFinding], ExtractionStats]:
    documents, stats = extract_packages(packages, progress_callback=progress_callback)
    if progress_callback:
        progress_callback(42, "checking_policy_rules")
    findings = evaluate_all_rules(packages, documents)
    if progress_callback:
        progress_callback(48, "engineering_features")
    rows = build_feature_rows(packages, documents, findings)
    return rows, documents, findings, stats


def _merge_warnings(*groups: list[str]) -> list[str]:
    warnings: list[str] = []
    for group in groups:
        warnings.extend(group)
    return list(dict.fromkeys(warnings))


def _persist_result(
    session: Session,
    *,
    run: ModelRun,
    result_type: str,
    evaluation: KycKybSplitEvaluation,
    explanation: dict[str, Any],
    packages: list[KycKybPackageRecord],
    documents: list[KycKybExtractedDocument],
    findings: list[KycKybRuleFinding],
    extraction_stats: ExtractionStats,
    warnings: list[str],
    audit_action: str,
    actor: str,
) -> None:
    all_warnings = _merge_warnings(warnings, extraction_stats.warnings)
    summary = _summary(
        packages=packages,
        documents=documents,
        findings=findings,
        evaluation=evaluation,
        extraction_stats=extraction_stats,
        warnings=all_warnings,
    )
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
                packages=packages,
                documents=documents,
                findings=findings,
                warnings=all_warnings,
            ),
            explanation=explanation,
        )
    )
    if result_type == KYC_KYB_VAL_RESULT_TYPE:
        session.add(
            ModelArtifact(
                use_case_slug=USE_CASE_SLUG,
                artifact_type="autogluon_model_directory",
                local_path="models/kyc-kyb/autogluon",
                metadata_json={
                    "provider": "local-autogluon",
                    "primary_metric": "average_precision",
                    "target": "label_manual_review_required",
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
                "package_count": len(packages),
            },
        )
    )
    session.commit()


def _create_kyc_kyb_run(session: Session) -> ModelRun:
    _ensure_datasets_seeded(session)
    run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="ocr-rules-autogluon-gpt4o-fallback",
        provider_used="local-ocr-rules-autogluon",
        model_name="pdfplumber/PyMuPDF/openpyxl + autogluon.tabular.TabularPredictor",
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    set_run_progress(run.id, 0, "queued")
    return run


def _scaled_progress(callback: ProgressCallback, start: int, end: int) -> ProgressCallback:
    span = max(end - start, 1)

    def on_progress(percent: int, stage: str) -> None:
        callback(start + int(max(0, min(100, percent)) / 100 * span), stage)

    return on_progress


def _run_validation_task(run_id: str, startup_progress_callback: ProgressCallback | None = None) -> None:
    with Session(engine) as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            return
        try:
            set_run_progress(run_id, 1, "loading_kyc_kyb_data")
            if startup_progress_callback:
                startup_progress_callback(1, "loading_kyc_kyb_data")

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)
                if startup_progress_callback:
                    startup_progress_callback(percent, stage)

            train_packages = load_train_packages()
            val_packages = load_val_packages()
            on_progress(4, "extracting_train_documents")
            train_rows, _, _, train_stats = _prepare_rows(
                train_packages,
                progress_callback=_scaled_progress(on_progress, 5, 28),
            )
            on_progress(29, "extracting_validation_documents")
            val_rows, val_documents, val_findings, val_stats = _prepare_rows(
                val_packages,
                progress_callback=_scaled_progress(on_progress, 30, 45),
            )
            _, val_evaluation, explanation = train_and_validate(
                train_rows,
                val_rows,
                progress_callback=_scaled_progress(on_progress, 46, 88),
                force_retrain=True,
            )
            combined_stats = ExtractionStats(
                fallback_count=train_stats.fallback_count + val_stats.fallback_count,
                timeout_count=train_stats.timeout_count + val_stats.timeout_count,
                invalid_json_count=train_stats.invalid_json_count + val_stats.invalid_json_count,
                warnings=_merge_warnings(train_stats.warnings, val_stats.warnings),
            )
            on_progress(94, "saving_results")
            _persist_result(
                session,
                run=run,
                result_type=KYC_KYB_VAL_RESULT_TYPE,
                evaluation=val_evaluation,
                explanation=explanation,
                packages=val_packages,
                documents=val_documents,
                findings=val_findings,
                extraction_stats=combined_stats,
                warnings=[],
                audit_action="kyc_kyb_validation_completed",
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
            set_run_progress(run_id, 5, "loading_test_packages")

            def on_progress(percent: int, stage: str) -> None:
                set_run_progress(run_id, percent, stage)

            test_packages = load_test_packages()
            test_rows, test_documents, test_findings, test_stats = _prepare_rows(
                test_packages,
                progress_callback=_scaled_progress(on_progress, 8, 38),
            )
            test_evaluation, explanation = evaluate_test(test_rows, progress_callback=_scaled_progress(on_progress, 42, 82))
            on_progress(93, "saving_results")
            _persist_result(
                session,
                run=run,
                result_type=KYC_KYB_TEST_RESULT_TYPE,
                evaluation=test_evaluation,
                explanation=explanation,
                packages=test_packages,
                documents=test_documents,
                findings=test_findings,
                extraction_stats=test_stats,
                warnings=[],
                audit_action="kyc_kyb_test_completed",
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


def run_kyc_kyb_startup(progress_callback: ProgressCallback | None = None) -> str:
    with Session(engine) as session:
        run = _create_kyc_kyb_run(session)
        run_id = run.id
    _run_validation_task(run_id, progress_callback)
    return run_id


def start_kyc_kyb_run(session: Session) -> dict:
    run = _create_kyc_kyb_run(session)
    enqueue_user_job(f"kyc-kyb-test-{run.id}", lambda: _run_test_task(run.id))
    return {"run_id": run.id, "status": "running"}


def get_kyc_kyb_run_progress(run_id: str, session: Session) -> dict:
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


def get_kyc_kyb_run_result(run_id: str, session: Session) -> dict:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != USE_CASE_SLUG:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status == "running":
        raise HTTPException(status_code=202, detail="Run is still in progress.")
    result = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.run_id == run_id,
            ProcessedResult.result_type.in_((KYC_KYB_VAL_RESULT_TYPE, KYC_KYB_TEST_RESULT_TYPE)),
        )
    ).first()
    if result is None and run.status == "failed":
        raise HTTPException(status_code=500, detail=run.error_message or "Run failed.")
    if result is None:
        raise HTTPException(status_code=404, detail="Run result not found.")
    return {"run": run.model_dump(), "result": result.model_dump()}
