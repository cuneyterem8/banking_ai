from pathlib import Path

from app.use_cases.market_intelligence.data_generation import write_artifacts
from app.use_cases.market_intelligence.raw_data import (
    load_calendar_events,
    load_competitor_rates,
    load_evaluation_cases,
    load_ground_truth,
    load_manifest,
    load_news,
    load_rates,
    load_taxonomy,
    raw_artifact_paths,
)


def test_market_intelligence_data_generation_creates_expected_artifacts() -> None:
    paths = write_artifacts()
    manifest = load_manifest()
    ground_truth = load_ground_truth()

    assert all(Path(path).exists() for path in paths.values())
    assert manifest["news_count"] == 180
    assert manifest["rate_record_count"] == 180
    assert manifest["competitor_rate_count"] == 80
    assert manifest["calendar_event_count"] == 36
    assert manifest["evaluation_case_count"] == 8
    assert ground_truth["evaluation_case_count"] == 8

    assert len(load_news()) == 180
    assert len(load_rates()) == 180
    assert len(load_competitor_rates()) == 80
    assert len(load_calendar_events()) == 36
    assert len(load_evaluation_cases()) == 8
    assert len(load_taxonomy()["topics"]) >= 8
    assert len(raw_artifact_paths()) == 9
