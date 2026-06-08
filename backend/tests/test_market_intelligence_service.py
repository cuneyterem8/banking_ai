import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.config import get_settings
from app.db.models import AuditEvent, ModelRun, ProcessedResult, RawArtifact, RawDataset
from app.services.seeding import seed_market_intelligence, seed_use_cases
from app.use_cases.market_intelligence.raw_data import DATASET_KEY_MARKET_INPUTS, USE_CASE_SLUG
from app.use_cases.market_intelligence.schemas import MarketResearchRequest
from app.use_cases.market_intelligence.service import (
    MARKET_RESEARCH_RESULT_TYPE,
    research_market_intelligence,
)


def test_market_seeding_stores_dataset_and_artifacts(session) -> None:
    seed_use_cases(session)
    seed_market_intelligence(session)

    dataset = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == DATASET_KEY_MARKET_INPUTS,
        )
    ).first()
    artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == USE_CASE_SLUG)).all()

    assert dataset is not None
    assert dataset.payload["news_count"] == 180
    assert dataset.payload["rate_record_count"] == 180
    assert dataset.payload["competitor_rate_count"] == 80
    assert dataset.payload["calendar_event_count"] == 36
    assert dataset.payload["evaluation_case_count"] == 8
    assert len(dataset.payload["news"]) == 180
    assert len(artifacts) == 9


def test_live_research_requires_openai_key_when_live_web_enabled(session, monkeypatch) -> None:
    seed_use_cases(session)
    seed_market_intelligence(session)
    settings = get_settings()
    original = settings.openai_api_key
    monkeypatch.setattr(settings, "openai_api_key", None)

    try:
        with pytest.raises(HTTPException) as exc:
            research_market_intelligence(
                session,
                MarketResearchRequest(objective="Research current deposit pricing.", use_live_web=True),
            )
    finally:
        monkeypatch.setattr(settings, "openai_api_key", original)

    assert exc.value.status_code == 409


def test_synthetic_market_research_persists_run_result_and_audit(session, monkeypatch) -> None:
    seed_use_cases(session)
    seed_market_intelligence(session)
    settings = get_settings()
    original = settings.openai_api_key
    monkeypatch.setattr(settings, "openai_api_key", None)

    try:
        response = research_market_intelligence(
            session,
            MarketResearchRequest(
                objective="Research synthetic rate and credit signals.",
                focus_areas=["rates", "credit", "regulation"],
                max_search_calls=0,
                use_live_web=False,
            ),
        )
    finally:
        monkeypatch.setattr(settings, "openai_api_key", original)

    run = session.get(ModelRun, response["run"]["id"])
    result = session.exec(
        select(ProcessedResult).where(
            ProcessedResult.run_id == response["run"]["id"],
            ProcessedResult.result_type == MARKET_RESEARCH_RESULT_TYPE,
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
    assert result.payload["summary"]["provider_used"] == "synthetic-corpus-fallback"
    assert result.payload["signals"]
    assert result.payload["sources"]
    assert audit is not None
