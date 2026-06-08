from app.use_cases.market_intelligence.agents import build_query_plan, run_market_intelligence_workflow
from app.use_cases.market_intelligence.schemas import MarketResearchRequest


def test_market_query_planner_respects_depth_bounds() -> None:
    quick = build_query_plan(MarketResearchRequest(depth="quick", max_search_calls=10))
    standard = build_query_plan(MarketResearchRequest(depth="standard", max_search_calls=10))
    deep = build_query_plan(MarketResearchRequest(depth="deep", max_search_calls=10))

    assert len(quick) == 4
    assert len(standard) == 6
    assert len(deep) == 8
    assert {query.focus_area for query in standard}


def test_market_workflow_with_mocked_search_persists_public_trace_shape() -> None:
    def search_client(query, _request):
        return {
            "sources": [
                {
                    "source_id": f"LIVE-{query.query_id}",
                    "title": f"Live source for {query.focus_area}",
                    "url": f"https://example.com/{query.query_id}",
                    "snippet": "A live cited source says banking teams should watch rate and credit signals.",
                    "published_at": "2026-06-08",
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": f"EV-{query.query_id}",
                    "source_id": f"LIVE-{query.query_id}",
                    "topic": query.focus_area,
                    "impact_area": "deposit_pricing",
                    "claim": "Deposit pricing pressure is increasing for synthetic banks.",
                    "sentiment": "watch",
                    "urgency": "high",
                    "confidence": 0.82,
                    "source_url": f"https://example.com/{query.query_id}",
                }
            ],
        }

    payload = run_market_intelligence_workflow(
        MarketResearchRequest(
            objective="Assess current deposit and credit signals.",
            focus_areas=["rates", "deposits", "credit", "regulation"],
            max_search_calls=4,
            use_live_web=True,
        ),
        search_client=search_client,
    )

    assert payload.summary.provider_used == "openai-web-search"
    assert payload.summary.live_source_count == 4
    assert payload.summary.signal_count > 0
    assert payload.briefs[0].cited_source_ids
    assert {step.agent_name for step in payload.agent_trace} >= {
        "Research Orchestrator",
        "Query Planner",
        "Search Scout",
        "Evidence Extractor",
        "Source Verifier",
        "Signal Scorer",
        "Executive Synthesizer",
        "Citation Reviewer",
    }
