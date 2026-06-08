"""Reset ML runs in the database before a fresh training cycle."""

from sqlmodel import Session, select

from app.db.models import AuditEvent, ModelArtifact, ModelRun, ProcessedResult
from app.use_cases.aml_monitoring.raw_data import USE_CASE_SLUG as AML_USE_CASE_SLUG
from app.use_cases.aml_monitoring.service import AML_TEST_RESULT_TYPE, AML_VAL_RESULT_TYPE
from app.use_cases.credit_risk.raw_data import USE_CASE_SLUG as CREDIT_USE_CASE_SLUG
from app.use_cases.credit_risk.service import CREDIT_TEST_RESULT_TYPE, CREDIT_VAL_RESULT_TYPE
from app.use_cases.document_ocr.raw_data import USE_CASE_SLUG as DOCUMENT_OCR_USE_CASE_SLUG
from app.use_cases.document_ocr.service import DOCUMENT_OCR_RESULT_TYPE
from app.use_cases.email_automation.raw_data import USE_CASE_SLUG as EMAIL_USE_CASE_SLUG
from app.use_cases.email_automation.service import EMAIL_AUTOMATION_DRAFT_RESULT_TYPE, EMAIL_AUTOMATION_EVAL_RESULT_TYPE
from app.use_cases.fraud_detection.raw_data import USE_CASE_SLUG
from app.use_cases.fraud_detection.service import FRAUD_TEST_RESULT_TYPE, FRAUD_VAL_RESULT_TYPE
from app.use_cases.kyc_kyb.raw_data import USE_CASE_SLUG as KYC_KYB_USE_CASE_SLUG
from app.use_cases.kyc_kyb.service import KYC_KYB_TEST_RESULT_TYPE, KYC_KYB_VAL_RESULT_TYPE
from app.use_cases.liquidity_forecast.raw_data import USE_CASE_SLUG as LIQUIDITY_USE_CASE_SLUG
from app.use_cases.liquidity_forecast.service import LIQUIDITY_FORECAST_RESULT_TYPE
from app.use_cases.market_intelligence.raw_data import USE_CASE_SLUG as MARKET_USE_CASE_SLUG
from app.use_cases.market_intelligence.service import MARKET_DAILY_RESULT_TYPE, MARKET_RESEARCH_RESULT_TYPE
from app.use_cases.support_chatbot.raw_data import USE_CASE_SLUG as SUPPORT_USE_CASE_SLUG
from app.use_cases.support_chatbot.service import SUPPORT_CHAT_RESULT_TYPE, SUPPORT_EVAL_RESULT_TYPE

TEST_COMPLETED_ACTION = "fraud_detection_test_completed"
VAL_COMPLETED_ACTION = "fraud_training_completed"
CREDIT_TEST_COMPLETED_ACTION = "credit_risk_test_completed"
CREDIT_VAL_COMPLETED_ACTION = "credit_training_completed"
AML_TEST_COMPLETED_ACTION = "aml_monitoring_test_completed"
AML_VAL_COMPLETED_ACTION = "aml_monitoring_validation_completed"
KYC_KYB_TEST_COMPLETED_ACTION = "kyc_kyb_test_completed"
KYC_KYB_VAL_COMPLETED_ACTION = "kyc_kyb_validation_completed"
EMAIL_AUTOMATION_DRAFT_COMPLETED_ACTION = "email_automation_draft_completed"
EMAIL_AUTOMATION_EVAL_COMPLETED_ACTION = "email_automation_evaluation_completed"
STARTUP_USE_CASE_SLUGS = (
    USE_CASE_SLUG,
    CREDIT_USE_CASE_SLUG,
    DOCUMENT_OCR_USE_CASE_SLUG,
    SUPPORT_USE_CASE_SLUG,
    LIQUIDITY_USE_CASE_SLUG,
    AML_USE_CASE_SLUG,
    KYC_KYB_USE_CASE_SLUG,
    EMAIL_USE_CASE_SLUG,
    MARKET_USE_CASE_SLUG,
)
STARTUP_RESULT_TYPES = {
    USE_CASE_SLUG: (FRAUD_VAL_RESULT_TYPE, FRAUD_TEST_RESULT_TYPE),
    CREDIT_USE_CASE_SLUG: (CREDIT_VAL_RESULT_TYPE, CREDIT_TEST_RESULT_TYPE),
    DOCUMENT_OCR_USE_CASE_SLUG: (DOCUMENT_OCR_RESULT_TYPE,),
    SUPPORT_USE_CASE_SLUG: (SUPPORT_EVAL_RESULT_TYPE, SUPPORT_CHAT_RESULT_TYPE),
    LIQUIDITY_USE_CASE_SLUG: (LIQUIDITY_FORECAST_RESULT_TYPE,),
    AML_USE_CASE_SLUG: (AML_VAL_RESULT_TYPE, AML_TEST_RESULT_TYPE),
    KYC_KYB_USE_CASE_SLUG: (KYC_KYB_VAL_RESULT_TYPE, KYC_KYB_TEST_RESULT_TYPE),
    EMAIL_USE_CASE_SLUG: (EMAIL_AUTOMATION_EVAL_RESULT_TYPE, EMAIL_AUTOMATION_DRAFT_RESULT_TYPE),
    MARKET_USE_CASE_SLUG: (MARKET_DAILY_RESULT_TYPE, MARKET_RESEARCH_RESULT_TYPE),
}


def _delete_run(
    session: Session,
    run_id: str,
    *,
    use_case_slug: str,
    audit_actions: tuple[str, ...] | None,
) -> bool:
    run = session.get(ModelRun, run_id)
    if run is None or run.use_case_slug != use_case_slug:
        return False

    for result in session.exec(select(ProcessedResult).where(ProcessedResult.run_id == run_id)).all():
        session.delete(result)
    event_query = select(AuditEvent).where(
        AuditEvent.entity_type == "model_run",
        AuditEvent.entity_id == run_id,
    )
    if audit_actions is not None:
        event_query = event_query.where(AuditEvent.action.in_(audit_actions))
    for event in session.exec(event_query).all():
        session.delete(event)
    session.delete(run)
    return True


def clear_use_case_outputs(session: Session, use_case_slug: str) -> int:
    result_types = STARTUP_RESULT_TYPES.get(use_case_slug, ())
    run_ids: set[str] = {
        item.run_id
        for item in session.exec(
            select(ProcessedResult).where(
                ProcessedResult.use_case_slug == use_case_slug,
                ProcessedResult.result_type.in_(result_types),
            )
        ).all()
    }
    run_ids.update(run.id for run in session.exec(select(ModelRun).where(ModelRun.use_case_slug == use_case_slug)).all())

    removed = 0
    for run_id in run_ids:
        if _delete_run(session, run_id, use_case_slug=use_case_slug, audit_actions=None):
            removed += 1

    for artifact in session.exec(select(ModelArtifact).where(ModelArtifact.use_case_slug == use_case_slug)).all():
        session.delete(artifact)

    for event in session.exec(
        select(AuditEvent).where(
            AuditEvent.entity_type == "use_case",
            AuditEvent.entity_id == use_case_slug,
        )
    ).all():
        session.delete(event)

    session.commit()
    return removed


def reset_startup_outputs(session: Session) -> None:
    for use_case_slug in STARTUP_USE_CASE_SLUGS:
        clear_use_case_outputs(session, use_case_slug)


def clear_fraud_test_runs(session: Session) -> int:
    """Remove test-split runs and their results."""
    test_results = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.use_case_slug == USE_CASE_SLUG,
            ProcessedResult.result_type == FRAUD_TEST_RESULT_TYPE,
        )
    ).all()
    run_ids: set[str] = {item.run_id for item in test_results}

    fraud_runs = session.exec(select(ModelRun).where(ModelRun.use_case_slug == USE_CASE_SLUG)).all()
    for run in fraud_runs:
        split = (run.metrics or {}).get("split")
        if split == "test":
            run_ids.add(run.id)
        elif split != "val" and run.status in {"running", "completed", "failed"}:
            run_ids.add(run.id)

    removed = 0
    for run_id in run_ids:
        if _delete_run(session, run_id, use_case_slug=USE_CASE_SLUG, audit_actions=(TEST_COMPLETED_ACTION,)):
            removed += 1

    if removed:
        session.commit()
    return removed


def clear_fraud_val_runs(session: Session) -> int:
    """Remove validation (startup training) runs and their results."""
    val_results = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.use_case_slug == USE_CASE_SLUG,
            ProcessedResult.result_type == FRAUD_VAL_RESULT_TYPE,
        )
    ).all()
    run_ids: set[str] = {item.run_id for item in val_results}

    for run in session.exec(select(ModelRun).where(ModelRun.use_case_slug == USE_CASE_SLUG)).all():
        if (run.metrics or {}).get("split") == "val":
            run_ids.add(run.id)

    removed = 0
    for run_id in run_ids:
        if _delete_run(session, run_id, use_case_slug=USE_CASE_SLUG, audit_actions=(VAL_COMPLETED_ACTION,)):
            removed += 1

    if removed:
        session.commit()
    return removed


def reset_fraud_for_training(session: Session) -> None:
    """Wipe prior val/test predictions and model artifact rows before training from scratch."""
    clear_fraud_test_runs(session)
    clear_fraud_val_runs(session)
    for artifact in session.exec(
        select(ModelArtifact).where(ModelArtifact.use_case_slug == USE_CASE_SLUG)
    ).all():
        session.delete(artifact)
    session.commit()


def clear_credit_test_runs(session: Session) -> int:
    test_results = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.use_case_slug == CREDIT_USE_CASE_SLUG,
            ProcessedResult.result_type == CREDIT_TEST_RESULT_TYPE,
        )
    ).all()
    run_ids: set[str] = {item.run_id for item in test_results}
    for run in session.exec(select(ModelRun).where(ModelRun.use_case_slug == CREDIT_USE_CASE_SLUG)).all():
        split = (run.metrics or {}).get("split")
        if split == "test":
            run_ids.add(run.id)
        elif split != "val" and run.status in {"running", "completed", "failed"}:
            run_ids.add(run.id)

    removed = 0
    for run_id in run_ids:
        if _delete_run(session, run_id, use_case_slug=CREDIT_USE_CASE_SLUG, audit_actions=(CREDIT_TEST_COMPLETED_ACTION,)):
            removed += 1
    if removed:
        session.commit()
    return removed


def clear_credit_val_runs(session: Session) -> int:
    val_results = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.use_case_slug == CREDIT_USE_CASE_SLUG,
            ProcessedResult.result_type == CREDIT_VAL_RESULT_TYPE,
        )
    ).all()
    run_ids: set[str] = {item.run_id for item in val_results}
    for run in session.exec(select(ModelRun).where(ModelRun.use_case_slug == CREDIT_USE_CASE_SLUG)).all():
        if (run.metrics or {}).get("split") == "val":
            run_ids.add(run.id)

    removed = 0
    for run_id in run_ids:
        if _delete_run(session, run_id, use_case_slug=CREDIT_USE_CASE_SLUG, audit_actions=(CREDIT_VAL_COMPLETED_ACTION,)):
            removed += 1
    if removed:
        session.commit()
    return removed


def reset_credit_for_training(session: Session) -> None:
    clear_credit_test_runs(session)
    clear_credit_val_runs(session)
    for artifact in session.exec(
        select(ModelArtifact).where(ModelArtifact.use_case_slug == CREDIT_USE_CASE_SLUG)
    ).all():
        session.delete(artifact)
    session.commit()
