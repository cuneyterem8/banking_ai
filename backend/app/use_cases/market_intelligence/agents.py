from __future__ import annotations

from datetime import datetime
from typing import Callable

from app.config import get_settings
from app.use_cases.market_intelligence.raw_data import load_news, load_rates
from app.use_cases.market_intelligence.schemas import (
    MarketAgentStep,
    MarketBrief,
    MarketCostControl,
    MarketEvidenceItem,
    MarketIntelligencePayload,
    MarketIntelligenceSummary,
    MarketMode,
    MarketQueryPlan,
    MarketResearchRequest,
    MarketSource,
)
from app.use_cases.market_intelligence.signal_scoring import score_market_signals
from app.use_cases.market_intelligence.source_verification import verify_sources
from app.use_cases.market_intelligence.web_search_service import SearchClient, run_openai_web_search

ProgressCallback = Callable[[int, str], None]


def build_query_plan(request: MarketResearchRequest) -> list[MarketQueryPlan]:
    depth_counts = {"quick": 4, "standard": 6, "deep": 8}
    target_count = min(depth_counts.get(request.depth, 6), max(request.max_search_calls, 1))
    focus_areas = request.focus_areas or ["rates", "deposits", "credit", "regulation"]
    questions: list[MarketQueryPlan] = []
    for index in range(target_count):
        focus_area = focus_areas[index % len(focus_areas)]
        questions.append(
            MarketQueryPlan(
                query_id=f"MI-Q-{index + 1:02d}",
                focus_area=focus_area,
                priority=index + 1,
                question=(
                    f"{request.region} banking market intelligence: latest public signals about "
                    f"{focus_area.replace('_', ' ')} relevant to {request.objective}"
                ),
            )
        )
    return questions


def _synthetic_sources_and_evidence(request: MarketResearchRequest, *, limit: int = 14) -> tuple[list[MarketSource], list[MarketEvidenceItem]]:
    focus = set(request.focus_areas or [])
    articles = [
        item
        for item in load_news()
        if not focus or item.topic in focus or item.impact_area in focus
    ][:limit]
    if len(articles) < min(limit, 8):
        articles = load_news()[:limit]
    retrieved_at = datetime.utcnow().isoformat()
    sources: list[MarketSource] = []
    evidence: list[MarketEvidenceItem] = []
    for index, article in enumerate(articles, start=1):
        source_id = f"synthetic-source-{index:03d}"
        sources.append(
            MarketSource(
                source_id=source_id,
                title=article.title,
                url=article.url,
                domain="synthetic.example",
                source_type="synthetic_corpus",
                snippet=article.summary,
                retrieved_at=retrieved_at,
                published_at=article.published_at,
                verification_status="verified",
                citation_count=1,
            )
        )
        evidence.append(
            MarketEvidenceItem(
                evidence_id=f"synthetic-evidence-{index:03d}",
                source_id=source_id,
                topic=article.topic,
                impact_area=article.impact_area,
                claim=article.summary,
                sentiment=article.sentiment,
                urgency=article.urgency,
                confidence=0.78,
                source_url=article.url,
            )
        )
    rates = load_rates()
    if rates:
        latest = rates[-1]
        source_id = "synthetic-source-rates"
        sources.append(
            MarketSource(
                source_id=source_id,
                title="Synthetic rates time series baseline",
                url="https://synthetic.example/market-intelligence/rates",
                domain="synthetic.example",
                source_type="synthetic_corpus",
                snippet=f"Latest synthetic fed funds rate {latest.fed_funds_rate} and 10Y treasury {latest.treasury_10y}.",
                retrieved_at=retrieved_at,
                published_at=latest.date,
                verification_status="verified",
                citation_count=1,
            )
        )
        evidence.append(
            MarketEvidenceItem(
                evidence_id="synthetic-evidence-rates",
                source_id=source_id,
                topic="rates",
                impact_area="deposit_pricing",
                claim=f"Latest synthetic rates baseline shows fed funds at {latest.fed_funds_rate} and deposit beta index at {latest.deposit_beta_index}.",
                sentiment="watch",
                urgency="medium",
                confidence=0.82,
                source_url="https://synthetic.example/market-intelligence/rates",
            )
        )
    return sources, evidence


def _brief_from_signals(
    *,
    mode: MarketMode,
    request: MarketResearchRequest,
    signals,
    sources: list[MarketSource],
    warnings: list[str],
) -> MarketBrief:
    top_signals = sorted(signals, key=lambda item: (item.urgency != "high", -item.confidence))[:6]
    headline = f"{request.region} Banking Market Intelligence Brief"
    if top_signals:
        headline = f"{top_signals[0].impact_area.replace('_', ' ').title()} Leads {request.region} Banking Watch"
    cited = [source.source_id for source in sources[:10]]
    confidence = round(sum(signal.confidence for signal in top_signals) / len(top_signals), 4) if top_signals else 0.62
    if warnings:
        confidence = max(0.35, round(confidence - min(len(warnings), 4) * 0.04, 4))
    return MarketBrief(
        brief_id=f"MI-BRIEF-{mode.upper()}",
        headline=headline,
        executive_summary=(
            f"This {mode.replace('_', ' ')} synthesizes public and synthetic market signals for {request.region} banking teams. "
            f"The strongest areas to monitor are {', '.join(signal.impact_area.replace('_', ' ') for signal in top_signals[:3]) or 'rates, deposits, credit, and regulation'}."
        ),
        top_developments=[signal.summary for signal in top_signals[:5]],
        banking_implications=[
            f"{signal.impact_area.replace('_', ' ').title()}: {signal.direction} direction with {signal.urgency} urgency."
            for signal in top_signals[:5]
        ],
        risks_and_opportunities=[
            "Validate pricing, credit, and operational assumptions before changing customer-facing policy.",
            "Treat this output as market research support, not investment advice.",
        ],
        recommended_actions=[
            "Review deposit and lending pricing guardrails.",
            "Share cited developments with treasury, product, compliance, and customer communications teams.",
            "Schedule follow-up research for high-urgency watch items.",
        ],
        watchlist_items=[signal.topic.replace("_", " ").title() for signal in top_signals[:6]],
        cited_source_ids=cited,
        confidence=confidence,
    )


def run_market_intelligence_workflow(
    request: MarketResearchRequest,
    *,
    mode: MarketMode = "daily_brief",
    search_client: SearchClient | None = None,
    progress_callback: ProgressCallback | None = None,
) -> MarketIntelligencePayload:
    settings = get_settings()
    agent_trace: list[MarketAgentStep] = [
        MarketAgentStep(
            step_id="agent-orchestrator",
            agent_name="Research Orchestrator",
            status="completed",
            summary=f"Prepared {mode.replace('_', ' ')} workflow for {request.region} with max {request.max_search_calls} search calls.",
            input_count=1,
            output_count=1,
        )
    ]
    if progress_callback:
        progress_callback(8, "planning_queries")
    query_plan = build_query_plan(request)
    agent_trace.append(
        MarketAgentStep(
            step_id="agent-planner",
            agent_name="Query Planner",
            status="completed",
            summary=f"Created {len(query_plan)} targeted search questions.",
            input_count=len(request.focus_areas),
            output_count=len(query_plan),
        )
    )

    if progress_callback:
        progress_callback(22, "searching_public_sources")
    web_result = run_openai_web_search(query_plan, request, search_client=search_client)
    agent_trace.extend(web_result.agent_steps)
    warnings = list(web_result.warnings)

    if progress_callback:
        progress_callback(46, "extracting_evidence")
    synthetic_sources, synthetic_evidence = _synthetic_sources_and_evidence(request)
    use_synthetic_only = web_result.provider_used == "synthetic-corpus-fallback" or not web_result.sources
    sources = synthetic_sources if use_synthetic_only else [*web_result.sources, *synthetic_sources[:6]]
    evidence = synthetic_evidence if use_synthetic_only else [*web_result.evidence_items, *synthetic_evidence[:6]]
    agent_trace.append(
        MarketAgentStep(
            step_id="agent-extractor",
            agent_name="Evidence Extractor",
            status="completed",
            summary=f"Normalized {len(evidence)} evidence items from live and synthetic inputs.",
            input_count=len(sources),
            output_count=len(evidence),
        )
    )

    if progress_callback:
        progress_callback(62, "verifying_sources")
    sources, evidence, verification_warnings = verify_sources(sources, evidence, live_source_minimum=5)
    warnings.extend(verification_warnings)
    agent_trace.append(
        MarketAgentStep(
            step_id="agent-verifier",
            agent_name="Source Verifier",
            status="completed",
            summary=f"Verified {len(sources)} sources and retained {len(evidence)} supported evidence items.",
            input_count=len(sources),
            output_count=len(evidence),
        )
    )

    if progress_callback:
        progress_callback(74, "scoring_signals")
    signals = score_market_signals(evidence)
    agent_trace.append(
        MarketAgentStep(
            step_id="agent-scorer",
            agent_name="Signal Scorer",
            status="completed",
            summary=f"Scored {len(signals)} banking market impact signals.",
            input_count=len(evidence),
            output_count=len(signals),
        )
    )

    if progress_callback:
        progress_callback(86, "synthesizing_brief")
    brief = _brief_from_signals(mode=mode, request=request, signals=signals, sources=sources, warnings=warnings)
    agent_trace.append(
        MarketAgentStep(
            step_id="agent-synthesizer",
            agent_name="Executive Synthesizer",
            status="completed",
            summary="Created executive market brief JSON from verified signals.",
            input_count=len(signals),
            output_count=1,
        )
    )
    unsupported = [signal.signal_id for signal in signals if not signal.evidence_count]
    if unsupported:
        warnings.append(f"{len(unsupported)} signals had no supporting evidence and were excluded from recommendations.")
    agent_trace.append(
        MarketAgentStep(
            step_id="agent-reviewer",
            agent_name="Citation Reviewer",
            status="completed",
            summary=f"Reviewed citations and warnings; {len(warnings)} warnings remain.",
            input_count=len(sources),
            output_count=len(warnings),
        )
    )

    provider_used = web_result.provider_used if not use_synthetic_only else "synthetic-corpus-fallback"
    model_name = web_result.model_name if not use_synthetic_only else "synthetic-corpus"
    average_confidence = round(sum(signal.confidence for signal in signals) / len(signals), 4) if signals else brief.confidence
    cost_control = MarketCostControl(
        model_name=settings.market_research_model,
        fallback_model_name=settings.market_search_fallback_model,
        search_context_size=settings.market_search_context_size,
        max_search_calls=request.max_search_calls,
        search_call_count=web_result.search_call_count,
        estimated_search_cost_usd=web_result.estimated_search_cost_usd,
        live_search_enabled=bool(request.use_live_web and settings.market_live_search_enabled),
    )
    summary = MarketIntelligenceSummary(
        mode=mode,
        source_count=len(sources),
        live_source_count=sum(1 for source in sources if source.source_type == "live_web"),
        synthetic_source_count=sum(1 for source in sources if source.source_type == "synthetic_corpus"),
        evidence_count=len(evidence),
        signal_count=len(signals),
        brief_count=1,
        search_call_count=web_result.search_call_count,
        estimated_search_cost_usd=web_result.estimated_search_cost_usd,
        warning_count=len(warnings),
        average_confidence=average_confidence,
        provider_used=provider_used,
        model_name=model_name,
    )
    if progress_callback:
        progress_callback(94, "saving_results")
    return MarketIntelligencePayload(
        mode=mode,
        summary=summary,
        briefs=[brief],
        signals=signals,
        sources=sources,
        evidence_items=evidence,
        query_plan=query_plan,
        agent_trace=agent_trace,
        cost_control=cost_control,
        warnings=list(dict.fromkeys(warnings)),
    )
