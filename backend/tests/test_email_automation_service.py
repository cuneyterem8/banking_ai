from sqlmodel import select

from app.db.models import AuditEvent, ModelRun, ProcessedResult, RawArtifact, RawDataset
from app.services.seeding import seed_email_automation, seed_use_cases
from app.use_cases.email_automation import service
from app.use_cases.email_automation.llm_service import GeneratedDraft, GenerationStats
from app.use_cases.email_automation.raw_data import (
    DATASET_KEY_EMAIL_INPUTS,
    USE_CASE_SLUG,
    load_events,
    load_evaluation_cases,
)
from app.use_cases.email_automation.schemas import EmailDraftRequest
from app.use_cases.email_automation.service import (
    EMAIL_AUTOMATION_DRAFT_RESULT_TYPE,
    EMAIL_AUTOMATION_EVAL_RESULT_TYPE,
    draft_email,
    run_email_cases,
)


def _strict_payload(_case, _baseline):
    return {
        "subject": "Synthetic account update",
        "preheader": "A concise synthetic message.",
        "body": "Hello, this synthetic draft uses masked customer data and avoids full identifiers.",
        "call_to_action": "Review details",
        "tone_tags": ["clear", "professional"],
        "required_disclosures": ["This service message is not a marketing offer."],
        "personalization_used": ["first_name", "masked_account"],
        "confidence": 0.9,
    }


def test_email_run_cases_returns_evaluation_payload_with_metrics() -> None:
    payload = run_email_cases(load_evaluation_cases()[:3], ollama_client=_strict_payload)

    assert payload.mode == "evaluation"
    assert payload.summary.draft_count == 3
    assert payload.summary.provider_used == "local-ollama"
    assert payload.summary.average_quality_score > 0
    assert len(payload.drafts) == 3
    assert len(payload.scores) == 3


def test_email_seeding_stores_dataset_and_artifacts(session) -> None:
    seed_use_cases(session)
    seed_email_automation(session)

    dataset = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_EMAIL_INPUTS,
        )
    ).first()
    artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == USE_CASE_SLUG)).all()

    assert dataset is not None
    assert dataset.payload["customer_count"] == 120
    assert dataset.payload["service_event_count"] == 80
    assert dataset.payload["campaign_audience_count"] == 40
    assert dataset.payload["evaluation_case_count"] == 24
    assert len(dataset.payload["customers"]) == 120
    assert len(artifacts) == 10


def test_interactive_email_draft_persists_run_result_and_audit(session, monkeypatch) -> None:
    def fake_generate_email_draft(*, case, baseline, **_kwargs):
        return GeneratedDraft(
            draft=baseline.model_copy(
                update={
                    "provider_used": "local-ollama",
                    "model_name": "qwen-test",
                    "generation_status": "generated",
                    "confidence": 0.9,
                }
            ),
            stats=GenerationStats(),
        )

    seed_use_cases(session)
    seed_email_automation(session)
    monkeypatch.setattr(service, "generate_email_draft", fake_generate_email_draft)
    event = load_events()[0]
    response = draft_email(
        session,
        EmailDraftRequest(
            customer_id=event.customer_id,
            communication_type="service",
            event_type=event.event_type,
            custom_context="Synthetic branch callback requested.",
        ),
    )

    run = session.get(ModelRun, response["run"]["id"])
    result = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.run_id == response["run"]["id"],
            ProcessedResult.result_type == EMAIL_AUTOMATION_DRAFT_RESULT_TYPE,
        )
    ).first()
    audit = session.exec(
        select(AuditEvent).where(
            AuditEvent.entity_type == "model_run",
            AuditEvent.entity_id == response["run"]["id"],
        )
    ).first()

    assert run is not None
    assert run.status == "completed"
    assert result is not None
    assert result.payload["summary"]["draft_count"] == 1
    assert result.payload["mode"] == "draft"
    assert audit is not None


def test_email_evaluation_result_type_constant_is_stable() -> None:
    assert EMAIL_AUTOMATION_EVAL_RESULT_TYPE == "email_automation_evaluation"
