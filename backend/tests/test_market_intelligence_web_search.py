from app.use_cases.market_intelligence.schemas import MarketEvidenceItem, MarketSource
from app.use_cases.market_intelligence.source_verification import verify_sources
from app.use_cases.market_intelligence.web_search_service import extract_citations_from_response


def test_extract_citations_from_responses_annotations() -> None:
    response = {
        "output": [
            {
                "content": [
                    {
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/rates",
                                    "title": "Rate update",
                                    "snippet": "Short sourced excerpt.",
                                },
                            }
                        ]
                    }
                ]
            }
        ]
    }

    citations = extract_citations_from_response(response)

    assert citations == [
        {
            "url": "https://example.com/rates",
            "title": "Rate update",
            "snippet": "Short sourced excerpt.",
        }
    ]


def test_source_verifier_dedupes_urls_and_flags_unsupported_evidence() -> None:
    sources = [
        MarketSource(
            source_id="SRC-1",
            title="First",
            url="https://example.com/item",
            domain="example.com",
            source_type="live_web",
            snippet="One",
            retrieved_at="2026-06-08T00:00:00",
        ),
        MarketSource(
            source_id="SRC-2",
            title="Duplicate",
            url="https://example.com/item",
            domain="example.com",
            source_type="live_web",
            snippet="Two",
            retrieved_at="2026-06-08T00:00:00",
        ),
    ]
    evidence = [
        MarketEvidenceItem(
            evidence_id="EV-1",
            source_id="SRC-1",
            topic="rates",
            impact_area="deposit_pricing",
            claim="Deposit pricing pressure is rising.",
            sentiment="watch",
            urgency="medium",
            confidence=0.8,
            source_url="https://example.com/item",
        ),
        MarketEvidenceItem(
            evidence_id="EV-2",
            source_id="MISSING",
            topic="credit",
            impact_area="credit_risk",
            claim="Unsupported claim.",
            sentiment="negative",
            urgency="high",
            confidence=0.7,
        ),
    ]

    verified_sources, verified_evidence, warnings = verify_sources(sources, evidence, live_source_minimum=1)

    assert len(verified_sources) == 1
    assert len(verified_evidence) == 1
    assert verified_sources[0].citation_count == 1
    assert any("duplicate" in warning.lower() for warning in warnings)
    assert any("source support" in warning.lower() for warning in warnings)
