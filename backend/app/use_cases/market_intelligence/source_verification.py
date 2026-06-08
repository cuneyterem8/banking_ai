from __future__ import annotations

from urllib.parse import urlparse

from app.use_cases.market_intelligence.schemas import MarketEvidenceItem, MarketSource


def domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.") or "synthetic.example"


def verify_sources(
    sources: list[MarketSource],
    evidence_items: list[MarketEvidenceItem],
    *,
    live_source_minimum: int = 5,
) -> tuple[list[MarketSource], list[MarketEvidenceItem], list[str]]:
    warnings: list[str] = []
    seen_urls: set[str] = set()
    verified_sources: list[MarketSource] = []
    citation_counts: dict[str, int] = {}
    for evidence in evidence_items:
        citation_counts[evidence.source_id] = citation_counts.get(evidence.source_id, 0) + 1

    for source in sources:
        normalized_url = source.url.strip().lower()
        if normalized_url in seen_urls:
            warnings.append(f"Duplicate source skipped: {source.url}")
            continue
        seen_urls.add(normalized_url)
        citation_count = citation_counts.get(source.source_id, 0)
        status = "verified" if source.url and citation_count > 0 else "weak"
        if source.source_type == "live_web" and not source.published_at:
            status = "missing_date"
        verified_sources.append(
            source.model_copy(
                update={
                    "domain": domain_from_url(source.url),
                    "verification_status": status,
                    "citation_count": citation_count,
                }
            )
        )

    source_ids = {source.source_id for source in verified_sources}
    verified_evidence = [
        evidence
        for evidence in evidence_items
        if evidence.source_id in source_ids and (evidence.source_url or evidence.source_id.startswith("synthetic"))
    ]
    dropped = len(evidence_items) - len(verified_evidence)
    if dropped:
        warnings.append(f"{dropped} evidence items were dropped because they lacked source support.")

    live_count = sum(1 for source in verified_sources if source.source_type == "live_web")
    if live_count and live_count < live_source_minimum:
        warnings.append(f"Live brief has {live_count} distinct live sources; target is {live_source_minimum}.")

    return verified_sources, verified_evidence, list(dict.fromkeys(warnings))
