from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.config import get_settings
from app.use_cases.aml_monitoring.schemas import AmlAlertDecision, AmlNarrativeDraft

NarrativeClient = Callable[[AmlAlertDecision], dict[str, Any] | str | None]


@dataclass
class NarrativeStats:
    fallback_count: int = 0
    timeout_count: int = 0
    invalid_json_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class GeneratedNarrative:
    narrative: AmlNarrativeDraft
    stats: NarrativeStats


def _json_from_text(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _coerce_payload(payload: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        return _json_from_text(payload)
    if isinstance(payload, dict):
        return payload
    return None


def _prompt(alert: AmlAlertDecision) -> str:
    return (
        "You draft suspicious activity narrative notes for a synthetic AML training MVP. "
        "Use only the provided synthetic alert fields. Do not give legal advice or claim that a SAR must be filed. "
        "Return strict JSON with keys: narrative_status, alert_id, summary, suspicious_activity_type, "
        "evidence_bullets, recommended_next_steps, missing_information, confidence.\n\n"
        f"Alert ID: {alert.alert_id}\n"
        f"Customer ID: {alert.customer_id}\n"
        f"Account ID: {alert.account_id}\n"
        f"Typology: {alert.typology_tag}\n"
        f"SAR probability: {alert.sar_probability}\n"
        f"Risk level: {alert.risk_level}\n"
        f"Decision: {alert.decision}\n"
        f"Top factors: {json.dumps(alert.top_factors)}\n"
        f"Related entities: {json.dumps(alert.related_entities)}\n"
        f"Linked transaction count: {alert.linked_transaction_count}\n"
    )


def _call_with_timeout(callable_fn: Callable[[], dict[str, Any] | str | None], timeout_seconds: int) -> tuple[dict[str, Any] | str | None, bool]:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(callable_fn)
    try:
        result = future.result(timeout=timeout_seconds)
        executor.shutdown(wait=False, cancel_futures=False)
        return result, False
    except TimeoutError:
        executor.shutdown(wait=False, cancel_futures=True)
        return None, True
    except Exception:
        executor.shutdown(wait=False, cancel_futures=True)
        return None, False


def _ollama_available() -> bool:
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0)
        response.raise_for_status()
        models = response.json().get("models", [])
        names = {item.get("name") for item in models}
        return settings.ollama_model in names
    except Exception:
        return False


def _ollama_generate(alert: AmlAlertDecision) -> dict[str, Any] | str | None:
    settings = get_settings()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": _prompt(alert),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=settings.local_model_timeout_seconds,
    )
    response.raise_for_status()
    return response.json().get("response")


def _openai_generate(alert: AmlAlertDecision) -> dict[str, Any] | str | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        return None
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.local_model_timeout_seconds)
    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return strict JSON for a synthetic AML narrative draft."},
            {"role": "user", "content": _prompt(alert)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _narrative_from_payload(
    *,
    payload: dict[str, Any],
    alert: AmlAlertDecision,
    provider_used: str,
    model_name: str,
    warnings: list[str],
) -> AmlNarrativeDraft:
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = alert.sar_probability
    return AmlNarrativeDraft(
        narrative_status=str(payload.get("narrative_status") or "drafted"),
        alert_id=alert.alert_id,
        summary=str(payload.get("summary") or f"Synthetic {alert.typology_tag} alert prioritized for analyst review."),
        suspicious_activity_type=str(payload.get("suspicious_activity_type") or alert.typology_tag),
        evidence_bullets=_list_of_strings(payload.get("evidence_bullets")) or alert.top_factors,
        recommended_next_steps=_list_of_strings(payload.get("recommended_next_steps"))
        or ["Review linked synthetic transactions.", "Validate customer and entity context.", "Document analyst disposition."],
        missing_information=_list_of_strings(payload.get("missing_information")),
        confidence=max(0.0, min(1.0, float(confidence))),
        provider_used=provider_used,
        model_name=model_name,
        warnings=warnings,
    )


def _fallback_unavailable(alert: AmlAlertDecision, warnings: list[str]) -> AmlNarrativeDraft:
    return AmlNarrativeDraft(
        narrative_status="fallback_unavailable",
        alert_id=alert.alert_id,
        summary="The AML score was generated locally, but no LLM provider completed a structured narrative draft.",
        suspicious_activity_type=alert.typology_tag,
        evidence_bullets=alert.top_factors,
        recommended_next_steps=[
            "Configure Ollama Qwen or OPENAI_API_KEY to generate synthetic SAR narrative drafts.",
            "Review the scored alert manually using the local AML factors.",
        ],
        missing_information=["Narrative provider output is unavailable."],
        confidence=0,
        provider_used="fallback-unavailable",
        model_name="none",
        warnings=warnings,
    )


def draft_narrative(
    alert: AmlAlertDecision,
    *,
    ollama_client: NarrativeClient | None = None,
    openai_client: NarrativeClient | None = None,
) -> GeneratedNarrative:
    settings = get_settings()
    stats = NarrativeStats()
    should_try_ollama = ollama_client is not None or _ollama_available()
    if should_try_ollama:
        ollama_fn = lambda: ollama_client(alert) if ollama_client else _ollama_generate(alert)
        payload, timed_out = _call_with_timeout(ollama_fn, max(1, settings.local_model_timeout_seconds))
        if timed_out:
            stats.timeout_count += 1
            stats.warnings.append("Ollama Qwen timed out while drafting an AML narrative.")
        else:
            parsed = _coerce_payload(payload)
            if parsed:
                return GeneratedNarrative(
                    narrative=_narrative_from_payload(
                        payload=parsed,
                        alert=alert,
                        provider_used="local-ollama",
                        model_name=settings.ollama_model,
                        warnings=stats.warnings,
                    ),
                    stats=stats,
                )
            stats.invalid_json_count += 1
            stats.warnings.append("Ollama Qwen did not return valid structured AML narrative JSON.")
    else:
        stats.warnings.append("Ollama Qwen is unavailable; using GPT-4o fallback.")

    stats.fallback_count += 1
    openai_fn = lambda: openai_client(alert) if openai_client else _openai_generate(alert)
    payload, timed_out = _call_with_timeout(openai_fn, max(1, settings.local_model_timeout_seconds))
    if timed_out:
        stats.timeout_count += 1
        stats.warnings.append("GPT-4o fallback timed out while drafting an AML narrative.")
    parsed = _coerce_payload(payload)
    if parsed:
        return GeneratedNarrative(
            narrative=_narrative_from_payload(
                payload=parsed,
                alert=alert,
                provider_used="gpt-4o-fallback",
                model_name=settings.openai_model,
                warnings=stats.warnings,
            ),
            stats=stats,
        )

    stats.invalid_json_count += 1
    stats.warnings.append("GPT-4o fallback was unavailable or did not return valid AML narrative JSON.")
    return GeneratedNarrative(narrative=_fallback_unavailable(alert, stats.warnings), stats=stats)


def draft_narratives_for_alerts(
    alerts: list[AmlAlertDecision],
    *,
    limit: int = 6,
    ollama_client: NarrativeClient | None = None,
    openai_client: NarrativeClient | None = None,
) -> tuple[list[AmlNarrativeDraft], NarrativeStats]:
    selected = sorted(alerts, key=lambda item: item.sar_probability, reverse=True)[:limit]
    aggregate = NarrativeStats()
    narratives: list[AmlNarrativeDraft] = []
    for alert in selected:
        generated = draft_narrative(alert, ollama_client=ollama_client, openai_client=openai_client)
        narratives.append(generated.narrative)
        aggregate.fallback_count += generated.stats.fallback_count
        aggregate.timeout_count += generated.stats.timeout_count
        aggregate.invalid_json_count += generated.stats.invalid_json_count
        aggregate.warnings.extend(generated.stats.warnings)
    aggregate.warnings = list(dict.fromkeys(aggregate.warnings))
    return narratives, aggregate
