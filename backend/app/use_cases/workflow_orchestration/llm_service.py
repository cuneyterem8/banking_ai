from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

import httpx

from app.config import get_settings
from app.use_cases.workflow_orchestration.schemas import (
    WorkflowCaseResult,
    WorkflowCaseSummary,
    WorkflowRoutingDecision,
    WorkflowStepResult,
)

SummaryClient = Callable[[WorkflowCaseResult, list[WorkflowStepResult], WorkflowRoutingDecision], dict[str, Any] | str | None]


@dataclass
class SummaryStats:
    fallback_count: int = 0
    timeout_count: int = 0
    invalid_json_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class GeneratedSummary:
    summary: WorkflowCaseSummary
    stats: SummaryStats


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


def _prompt(case_result: WorkflowCaseResult, steps: list[WorkflowStepResult], routing: WorkflowRoutingDecision) -> str:
    return (
        "You are summarizing a synthetic banking workflow orchestration case. Return strict JSON only. "
        "Do not approve, reject, send, transfer, or execute any real banking action. "
        "Deterministic workflow rules are authoritative; your summary is explanatory wording only. "
        "Required JSON keys: summary, recommended_wording, next_steps, confidence.\n\n"
        f"Case result: {case_result.model_dump_json()}\n"
        f"Routing decision: {routing.model_dump_json()}\n"
        f"Workflow steps: {json.dumps([step.model_dump() for step in steps])}"
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


@lru_cache(maxsize=1)
def _ollama_available() -> bool:
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0)
        response.raise_for_status()
        models = response.json().get("models", [])
        return settings.ollama_model in {item.get("name") for item in models}
    except Exception:
        return False


def _ollama_generate(case_result: WorkflowCaseResult, steps: list[WorkflowStepResult], routing: WorkflowRoutingDecision) -> dict[str, Any] | str | None:
    settings = get_settings()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": _prompt(case_result, steps, routing),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=settings.local_model_timeout_seconds,
    )
    response.raise_for_status()
    return response.json().get("response")


def _openai_generate(case_result: WorkflowCaseResult, steps: list[WorkflowStepResult], routing: WorkflowRoutingDecision) -> dict[str, Any] | str | None:
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
            {"role": "system", "content": "Return strict JSON for a synthetic banking workflow case summary."},
            {"role": "user", "content": _prompt(case_result, steps, routing)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def _list_payload(payload: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        return fallback
    return [str(item) for item in raw if str(item).strip()]


def _summary_from_payload(
    *,
    payload: dict[str, Any],
    case_result: WorkflowCaseResult,
    routing: WorkflowRoutingDecision,
    provider_used: str,
    model_name: str,
    warnings: list[str],
) -> WorkflowCaseSummary:
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.72
    return WorkflowCaseSummary(
        case_id=case_result.case_id,
        summary_status="generated",
        summary=str(payload.get("summary") or _templated_summary_text(case_result, routing)),
        recommended_wording=str(payload.get("recommended_wording") or _templated_wording(case_result)),
        next_steps=_list_payload(payload, "next_steps", case_result.next_best_actions),
        confidence=max(0, min(1, float(confidence))),
        provider_used=provider_used,
        model_name=model_name,
        warnings=warnings,
    )


def _templated_summary_text(case_result: WorkflowCaseResult, routing: WorkflowRoutingDecision) -> str:
    return (
        f"{case_result.case_id} is a {case_result.workflow_type.replace('_', ' ')} workflow for "
        f"{case_result.subject_name}. The deterministic orchestrator set final status to "
        f"{routing.final_status}, assigned {routing.recommended_owner}, and classified risk as {routing.risk_level}."
    )


def _templated_wording(case_result: WorkflowCaseResult) -> str:
    return (
        f"Review {case_result.case_id} with the recommended owner, follow the listed next best actions, "
        "and keep the synthetic audit trail updated before closing the workflow."
    )


def generate_case_summary(
    *,
    case_result: WorkflowCaseResult,
    steps: list[WorkflowStepResult],
    routing: WorkflowRoutingDecision,
    ollama_client: SummaryClient | None = None,
    openai_client: SummaryClient | None = None,
) -> GeneratedSummary:
    settings = get_settings()
    stats = SummaryStats()
    should_try_ollama = ollama_client is not None or _ollama_available()
    if should_try_ollama:
        ollama_fn = lambda: ollama_client(case_result, steps, routing) if ollama_client else _ollama_generate(case_result, steps, routing)
        ollama_payload, timed_out = _call_with_timeout(ollama_fn, max(1, settings.local_model_timeout_seconds))
        if timed_out:
            stats.timeout_count += 1
            stats.warnings.append("Ollama Qwen timed out while summarizing a workflow case.")
        else:
            parsed = _coerce_payload(ollama_payload)
            if parsed:
                return GeneratedSummary(
                    summary=_summary_from_payload(
                        payload=parsed,
                        case_result=case_result,
                        routing=routing,
                        provider_used="local-ollama",
                        model_name=settings.ollama_model,
                        warnings=stats.warnings,
                    ),
                    stats=stats,
                )
            stats.invalid_json_count += 1
            stats.warnings.append("Ollama Qwen did not return valid structured workflow summary JSON.")
    else:
        stats.warnings.append("Ollama Qwen is unavailable for workflow summaries.")

    stats.fallback_count += 1
    openai_fn = lambda: openai_client(case_result, steps, routing) if openai_client else _openai_generate(case_result, steps, routing)
    openai_payload, openai_timed_out = _call_with_timeout(openai_fn, max(1, settings.local_model_timeout_seconds))
    if openai_timed_out:
        stats.timeout_count += 1
        stats.warnings.append("GPT-4o fallback timed out while summarizing a workflow case.")
    parsed_openai = _coerce_payload(openai_payload)
    if parsed_openai:
        return GeneratedSummary(
            summary=_summary_from_payload(
                payload=parsed_openai,
                case_result=case_result,
                routing=routing,
                provider_used="gpt-4o-fallback",
                model_name=settings.openai_model,
                warnings=stats.warnings,
            ),
            stats=stats,
        )

    stats.invalid_json_count += 1
    stats.warnings.append("LLM workflow summary providers were unavailable; a deterministic summary was used.")
    return GeneratedSummary(
        summary=WorkflowCaseSummary(
            case_id=case_result.case_id,
            summary_status="templated_fallback",
            summary=_templated_summary_text(case_result, routing),
            recommended_wording=_templated_wording(case_result),
            next_steps=case_result.next_best_actions,
            confidence=0.66,
            provider_used="fallback-unavailable",
            model_name="deterministic_template",
            warnings=stats.warnings,
        ),
        stats=stats,
    )
