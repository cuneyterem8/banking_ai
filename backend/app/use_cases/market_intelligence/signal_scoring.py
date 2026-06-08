from __future__ import annotations

from collections import defaultdict

from app.use_cases.market_intelligence.schemas import MarketEvidenceItem, MarketSignal


def _direction(sentiments: list[str]) -> str:
    if "negative" in sentiments and "positive" in sentiments:
        return "mixed"
    if "negative" in sentiments:
        return "negative"
    if "positive" in sentiments:
        return "positive"
    return "watch"


def _urgency(values: list[str]) -> str:
    if "high" in values:
        return "high"
    if "medium" in values:
        return "medium"
    return "low"


def score_market_signals(evidence_items: list[MarketEvidenceItem]) -> list[MarketSignal]:
    grouped: dict[str, list[MarketEvidenceItem]] = defaultdict(list)
    for item in evidence_items:
        grouped[item.impact_area].append(item)

    signals: list[MarketSignal] = []
    for index, (impact_area, items) in enumerate(sorted(grouped.items()), start=1):
        directions = [item.sentiment for item in items]
        urgency_values = [item.urgency for item in items]
        avg_confidence = round(sum(item.confidence for item in items) / len(items), 4) if items else 0
        top_topic = items[0].topic if items else impact_area
        signals.append(
            MarketSignal(
                signal_id=f"MI-SIGNAL-{index:03d}",
                topic=top_topic,
                sector="Banking",
                impact_area=impact_area,
                direction=_direction(directions),
                urgency=_urgency(urgency_values),
                confidence=avg_confidence,
                summary=(
                    f"{impact_area.replace('_', ' ').title()} shows {_direction(directions)} direction "
                    f"with {_urgency(urgency_values)} urgency based on {len(items)} evidence items."
                ),
                evidence_ids=[item.evidence_id for item in items[:6]],
                evidence_count=len(items),
            )
        )
    return signals
