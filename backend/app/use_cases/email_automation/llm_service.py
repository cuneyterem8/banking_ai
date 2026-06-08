from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.config import get_settings
from app.use_cases.email_automation.schemas import EmailAutomationDraft, EmailGenerationCase

LLMClient = Callable[[EmailGenerationCase, EmailAutomationDraft], dict[str, Any] | str | None]


@dataclass
class GenerationStats:
    fallback_count: int = 0
    timeout_count: int = 0
    invalid_json_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class GeneratedDraft:
    draft: EmailAutomationDraft
    stats: GenerationStats


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


def _prompt(case: EmailGenerationCase, baseline: EmailAutomationDraft) -> str:
    return (
        "You are drafting synthetic banking customer email content. Return strict JSON only. "
        "Do not send email. Do not include real data or full identifiers. Keep the draft compliant, concise, and in English. "
        "Required JSON keys: subject, preheader, body, call_to_action, tone_tags, required_disclosures, "
        "personalization_used, confidence.\n\n"
        f"Case ID: {case.case_id}\n"
        f"Communication type: {case.communication_type}\n"
        f"Event type: {case.event_type}\n"
        f"Campaign ID: {case.campaign_id}\n"
        f"Custom context: {case.custom_context}\n"
        f"Baseline subject: {baseline.subject}\n"
        f"Baseline preheader: {baseline.preheader}\n"
        f"Baseline body: {baseline.body}\n"
        f"Baseline CTA: {baseline.call_to_action}\n"
        f"Required disclosures: {json.dumps(case.expected_required_disclosures or baseline.required_disclosures)}"
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
        return settings.ollama_model in {item.get("name") for item in models}
    except Exception:
        return False


def _ollama_generate(case: EmailGenerationCase, baseline: EmailAutomationDraft) -> dict[str, Any] | str | None:
    settings = get_settings()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": _prompt(case, baseline),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=settings.local_model_timeout_seconds,
    )
    response.raise_for_status()
    return response.json().get("response")


def _openai_generate(case: EmailGenerationCase, baseline: EmailAutomationDraft) -> dict[str, Any] | str | None:
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
            {"role": "system", "content": "Return strict JSON for a synthetic banking email draft."},
            {"role": "user", "content": _prompt(case, baseline)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def _list_payload(payload: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        return fallback
    return [str(item) for item in raw if str(item).strip()]


def _draft_from_payload(
    *,
    payload: dict[str, Any],
    baseline: EmailAutomationDraft,
    provider_used: str,
    model_name: str,
    warnings: list[str],
) -> EmailAutomationDraft:
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = baseline.confidence
    return baseline.model_copy(
        update={
            "subject": str(payload.get("subject") or baseline.subject),
            "preheader": str(payload.get("preheader") or baseline.preheader),
            "body": str(payload.get("body") or baseline.body),
            "call_to_action": str(payload.get("call_to_action") or baseline.call_to_action),
            "provider_used": provider_used,
            "model_name": model_name,
            "generation_status": "generated",
            "confidence": max(0, min(1, float(confidence))),
            "tone_tags": _list_payload(payload, "tone_tags", baseline.tone_tags),
            "required_disclosures": _list_payload(payload, "required_disclosures", baseline.required_disclosures),
            "personalization_used": _list_payload(payload, "personalization_used", baseline.personalization_used),
            "warnings": warnings,
        }
    )


def generate_email_draft(
    *,
    case: EmailGenerationCase,
    baseline: EmailAutomationDraft,
    ollama_client: LLMClient | None = None,
    openai_client: LLMClient | None = None,
) -> GeneratedDraft:
    settings = get_settings()
    stats = GenerationStats()

    should_try_ollama = ollama_client is not None or _ollama_available()
    if should_try_ollama:
        ollama_fn = lambda: ollama_client(case, baseline) if ollama_client else _ollama_generate(case, baseline)
        ollama_payload, timed_out = _call_with_timeout(ollama_fn, max(1, settings.local_model_timeout_seconds))
        if timed_out:
            stats.timeout_count += 1
            stats.warnings.append("Ollama Qwen timed out while drafting an email.")
        else:
            parsed = _coerce_payload(ollama_payload)
            if parsed:
                return GeneratedDraft(
                    draft=_draft_from_payload(
                        payload=parsed,
                        baseline=baseline,
                        provider_used="local-ollama",
                        model_name=settings.ollama_model,
                        warnings=stats.warnings,
                    ),
                    stats=stats,
                )
            stats.invalid_json_count += 1
            stats.warnings.append("Ollama Qwen did not return valid structured email JSON.")
    else:
        stats.warnings.append("Ollama Qwen is unavailable; using GPT-4o fallback.")

    stats.fallback_count += 1
    openai_fn = lambda: openai_client(case, baseline) if openai_client else _openai_generate(case, baseline)
    openai_payload, openai_timed_out = _call_with_timeout(openai_fn, max(1, settings.local_model_timeout_seconds))
    if openai_timed_out:
        stats.timeout_count += 1
        stats.warnings.append("GPT-4o fallback timed out while drafting an email.")
    parsed_openai = _coerce_payload(openai_payload)
    if parsed_openai:
        return GeneratedDraft(
            draft=_draft_from_payload(
                payload=parsed_openai,
                baseline=baseline,
                provider_used="gpt-4o-fallback",
                model_name=settings.openai_model,
                warnings=stats.warnings,
            ),
            stats=stats,
        )

    stats.invalid_json_count += 1
    stats.warnings.append("GPT-4o fallback was unavailable or did not return valid structured email JSON.")
    return GeneratedDraft(
        draft=baseline.model_copy(
            update={
                "provider_used": "fallback-unavailable",
                "model_name": "template_engine",
                "generation_status": "fallback_unavailable",
                "warnings": stats.warnings,
            }
        ),
        stats=stats,
    )
