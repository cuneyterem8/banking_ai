from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.config import get_settings
from app.use_cases.market_intelligence.schemas import (
    MarketAgentStep,
    MarketEvidenceItem,
    MarketQueryPlan,
    MarketResearchRequest,
    MarketSource,
    SearchServiceResult,
)
from app.use_cases.market_intelligence.source_verification import domain_from_url

SearchClient = Callable[[MarketQueryPlan, MarketResearchRequest], dict[str, Any] | str | None]
WEB_SEARCH_ESTIMATED_COST_PER_CALL = 0.01


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return {}


def _output_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            return str(message.get("content") or "")
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text
    return ""


def extract_citations_from_response(response: Any) -> list[dict[str, str]]:
    payload = _as_mapping(response)
    citations: list[dict[str, str]] = []

    def add(value: Any) -> None:
        if not isinstance(value, dict):
            return
        citation = value.get("url_citation") if value.get("type") == "url_citation" else value
        if not isinstance(citation, dict):
            return
        url = citation.get("url")
        if not url:
            return
        citations.append(
            {
                "url": str(url),
                "title": str(citation.get("title") or domain_from_url(str(url))),
                "snippet": str(citation.get("snippet") or citation.get("text") or ""),
            }
        )

    for output in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        for content in output.get("content", []) if isinstance(output, dict) and isinstance(output.get("content"), list) else []:
            for annotation in content.get("annotations", []) if isinstance(content, dict) and isinstance(content.get("annotations"), list) else []:
                add(annotation)

    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            for annotation in message.get("annotations", []) if isinstance(message.get("annotations"), list) else []:
                add(annotation)

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for citation in citations:
        if citation["url"] in seen:
            continue
        seen.add(citation["url"])
        unique.append(citation)
    return unique


def _mock_or_live_response(
    query: MarketQueryPlan,
    request: MarketResearchRequest,
    search_client: SearchClient | None,
) -> tuple[Any, str, str, list[str]]:
    settings = get_settings()
    if search_client is not None:
        return search_client(query, request), "openai-web-search", settings.market_research_model, []
    if not settings.openai_api_key:
        return None, "synthetic-corpus-fallback", "synthetic-corpus", ["OpenAI API key is not configured; live web search was skipped."]
    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        return None, "synthetic-corpus-fallback", "synthetic-corpus", ["OpenAI Python package is unavailable; live web search was skipped."]

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.market_search_timeout_seconds)
    prompt = (
        "Return a concise banking market research answer with sourced citations. "
        "Focus only on public market information relevant to banks. "
        f"Region: {request.region}. Objective: {request.objective}. Search question: {query.question}"
    )
    try:
        response = client.responses.create(
            model=settings.market_research_model,
            tools=[{"type": "web_search", "search_context_size": settings.market_search_context_size}],
            input=prompt,
            reasoning={"effort": "low"},
        )
        return response, "openai-web-search", settings.market_research_model, []
    except Exception as responses_error:
        try:
            completion = client.chat.completions.create(
                model=settings.market_search_fallback_model,
                web_search_options={},
                messages=[{"role": "user", "content": prompt}],
            )
            return completion.model_dump(), "openai-web-search-fallback", settings.market_search_fallback_model, [
                f"Responses API web search failed; used fallback search model. Reason: {responses_error}"
            ]
        except Exception as fallback_error:
            return None, "synthetic-corpus-fallback", "synthetic-corpus", [
                f"OpenAI web search failed; synthetic corpus fallback will be used. Reason: {fallback_error}"
            ]


def _sources_from_structured_payload(
    payload: dict[str, Any],
    query: MarketQueryPlan,
    retrieved_at: str,
) -> tuple[list[MarketSource], list[MarketEvidenceItem]]:
    raw_sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    raw_evidence = payload.get("evidence_items") if isinstance(payload.get("evidence_items"), list) else []
    sources: list[MarketSource] = []
    evidence: list[MarketEvidenceItem] = []
    for index, item in enumerate(raw_sources, start=1):
        url = str(item.get("url") or f"https://synthetic.example/live/{query.query_id}/{index}")
        source_id = str(item.get("source_id") or f"LIVE-{query.query_id}-{index:02d}")
        sources.append(
            MarketSource(
                source_id=source_id,
                title=str(item.get("title") or query.question),
                url=url,
                domain=domain_from_url(url),
                source_type="live_web",
                query_id=query.query_id,
                query=query.question,
                snippet=str(item.get("snippet") or item.get("summary") or ""),
                retrieved_at=retrieved_at,
                published_at=item.get("published_at"),
            )
        )
    for index, item in enumerate(raw_evidence, start=1):
        evidence.append(
            MarketEvidenceItem(
                evidence_id=str(item.get("evidence_id") or f"EV-{query.query_id}-{index:02d}"),
                source_id=str(item.get("source_id") or (sources[0].source_id if sources else f"LIVE-{query.query_id}-01")),
                topic=str(item.get("topic") or query.focus_area),
                impact_area=str(item.get("impact_area") or "market_opportunity"),
                claim=str(item.get("claim") or item.get("summary") or query.question),
                sentiment=str(item.get("sentiment") or "watch"),
                urgency=str(item.get("urgency") or "medium"),
                confidence=float(item.get("confidence") or 0.72),
                source_url=item.get("source_url") or (sources[0].url if sources else None),
            )
        )
    return sources, evidence


def run_openai_web_search(
    query_plan: list[MarketQueryPlan],
    request: MarketResearchRequest,
    *,
    search_client: SearchClient | None = None,
) -> SearchServiceResult:
    settings = get_settings()
    if not request.use_live_web or not settings.market_live_search_enabled:
        return SearchServiceResult(
            provider_used="synthetic-corpus-fallback",
            model_name="synthetic-corpus",
            warnings=["Live web search is disabled for this run."],
        )

    max_calls = min(max(request.max_search_calls, 0), len(query_plan))
    if max_calls <= 0:
        return SearchServiceResult(
            provider_used="synthetic-corpus-fallback",
            model_name="synthetic-corpus",
            warnings=["No search budget was available; synthetic corpus fallback will be used."],
        )

    sources: list[MarketSource] = []
    evidence_items: list[MarketEvidenceItem] = []
    agent_steps: list[MarketAgentStep] = []
    warnings: list[str] = []
    provider_used = "openai-web-search"
    model_name = settings.market_research_model
    retrieved_at = datetime.utcnow().isoformat()

    for index, query in enumerate(query_plan[:max_calls], start=1):
        response, provider, model, response_warnings = _mock_or_live_response(query, request, search_client)
        provider_used = provider
        model_name = model
        warnings.extend(response_warnings)
        if response is None:
            continue
        payload = response if isinstance(response, dict) else _as_mapping(response)
        structured_sources, structured_evidence = _sources_from_structured_payload(payload, query, retrieved_at)
        citations = extract_citations_from_response(response)
        if structured_sources:
            sources.extend(structured_sources)
            evidence_items.extend(structured_evidence)
        elif citations:
            answer_text = _output_text(response)
            for citation_index, citation in enumerate(citations, start=1):
                source_id = f"LIVE-{query.query_id}-{citation_index:02d}"
                sources.append(
                    MarketSource(
                        source_id=source_id,
                        title=citation["title"],
                        url=citation["url"],
                        domain=domain_from_url(citation["url"]),
                        source_type="live_web",
                        query_id=query.query_id,
                        query=query.question,
                        snippet=citation["snippet"] or answer_text[:280],
                        retrieved_at=retrieved_at,
                    )
                )
                evidence_items.append(
                    MarketEvidenceItem(
                        evidence_id=f"EV-{query.query_id}-{citation_index:02d}",
                        source_id=source_id,
                        topic=query.focus_area,
                        impact_area="market_opportunity",
                        claim=answer_text[:420] or query.question,
                        sentiment="watch",
                        urgency="medium",
                        confidence=0.72,
                        source_url=citation["url"],
                    )
                )
        else:
            warnings.append(f"No citations were returned for query {query.query_id}.")

        agent_steps.append(
            MarketAgentStep(
                step_id=f"agent-search-{index:02d}",
                agent_name="Search Scout",
                status="completed",
                summary=f"Executed live web search for {query.focus_area}: {query.question}",
                input_count=1,
                output_count=len(citations) + len(structured_sources),
            )
        )

    search_call_count = max_calls if provider_used != "synthetic-corpus-fallback" else 0
    return SearchServiceResult(
        sources=sources,
        evidence_items=evidence_items,
        agent_steps=agent_steps,
        provider_used=provider_used,
        model_name=model_name,
        search_call_count=search_call_count,
        estimated_search_cost_usd=round(search_call_count * WEB_SEARCH_ESTIMATED_COST_PER_CALL, 4),
        warnings=list(dict.fromkeys(warnings)),
    )
