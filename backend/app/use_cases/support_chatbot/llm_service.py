from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.config import get_settings
from app.use_cases.support_chatbot.schemas import RetrievedSource, SupportChatbotAnswer

LLMClient = Callable[[str, list[RetrievedSource]], dict[str, Any] | str | None]


@dataclass
class GenerationStats:
    fallback_count: int = 0
    timeout_count: int = 0
    invalid_json_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class GeneratedAnswer:
    answer: SupportChatbotAnswer
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


def _prompt(question: str, retrieved_sources: list[RetrievedSource]) -> str:
    context = "\n\n".join(
        [
            f"SOURCE {index}\nsource_id: {source.source_id}\nsource_file: {source.source_file}\nchunk_id: {source.chunk_id}\ntitle: {source.title}\nquote: {source.quote}"
            for index, source in enumerate(retrieved_sources, start=1)
        ]
    )
    return (
        "You are an internal banking support assistant for synthetic training data. "
        "Answer only from the provided sources. If the answer is not present, say what is missing. "
        "Return strict JSON with keys: answer, confidence, sources, escalation_required, escalation_reason, "
        "policy_tags, missing_information. Each source must include source_id, source_file, chunk_id, title, quote.\n\n"
        f"Question: {question}\n\nRetrieved sources:\n{context}"
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


def _ollama_generate(question: str, sources: list[RetrievedSource]) -> dict[str, Any] | str | None:
    settings = get_settings()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": _prompt(question, sources),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=settings.local_model_timeout_seconds,
    )
    response.raise_for_status()
    return response.json().get("response")


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


def _openai_generate(question: str, sources: list[RetrievedSource]) -> dict[str, Any] | str | None:
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
            {"role": "system", "content": "Return strict JSON for an internal banking support answer."},
            {"role": "user", "content": _prompt(question, sources)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def _source_from_payload(raw_source: Any, retrieved_sources: list[RetrievedSource]) -> RetrievedSource | None:
    if not isinstance(raw_source, dict):
        return None
    source_id = str(raw_source.get("source_id") or "")
    chunk_id = str(raw_source.get("chunk_id") or "")
    for retrieved in retrieved_sources:
        if (source_id and retrieved.source_id == source_id) or (chunk_id and retrieved.chunk_id == chunk_id):
            return RetrievedSource(
                source_id=retrieved.source_id,
                source_file=retrieved.source_file,
                chunk_id=retrieved.chunk_id,
                title=str(raw_source.get("title") or retrieved.title),
                quote=str(raw_source.get("quote") or retrieved.quote)[:320],
                score=retrieved.score,
            )
    return None


def _answer_from_payload(
    *,
    payload: dict[str, Any],
    question_id: str | None,
    question: str,
    retrieved_sources: list[RetrievedSource],
    retrieval_confidence: float,
    provider_used: str,
    model_name: str,
) -> SupportChatbotAnswer:
    raw_sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    sources = [source for source in (_source_from_payload(item, retrieved_sources) for item in raw_sources) if source]
    if not sources:
        sources = retrieved_sources[:2]
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = retrieval_confidence
    raw_tags = payload.get("policy_tags") if isinstance(payload.get("policy_tags"), list) else []
    raw_missing = payload.get("missing_information") if isinstance(payload.get("missing_information"), list) else []
    return SupportChatbotAnswer(
        question_id=question_id,
        question=question,
        answer=str(payload.get("answer") or "The available synthetic support sources do not contain a complete answer."),
        answer_status="answered",
        provider_used=provider_used,
        model_name=model_name,
        confidence=max(0, min(1, float(confidence))),
        retrieval_confidence=retrieval_confidence,
        sources=sources,
        escalation_required=bool(payload.get("escalation_required", False)),
        escalation_reason=payload.get("escalation_reason") if payload.get("escalation_reason") else None,
        policy_tags=[str(item) for item in raw_tags if isinstance(item, str)],
        missing_information=[str(item) for item in raw_missing if isinstance(item, str)],
    )


def _fallback_unavailable_answer(
    *,
    question_id: str | None,
    question: str,
    retrieved_sources: list[RetrievedSource],
    retrieval_confidence: float,
    warnings: list[str],
) -> SupportChatbotAnswer:
    return SupportChatbotAnswer(
        question_id=question_id,
        question=question,
        answer="The support chatbot could retrieve relevant synthetic sources, but no LLM provider completed a structured answer.",
        answer_status="fallback_unavailable",
        provider_used="fallback-unavailable",
        model_name="none",
        confidence=0,
        retrieval_confidence=retrieval_confidence,
        sources=retrieved_sources[:2],
        missing_information=["Configure Ollama Qwen or OPENAI_API_KEY to generate support answers."],
        warnings=warnings,
    )


def answer_question(
    *,
    question: str,
    question_id: str | None,
    retrieved_sources: list[RetrievedSource],
    retrieval_confidence: float,
    ollama_client: LLMClient | None = None,
    openai_client: LLMClient | None = None,
) -> GeneratedAnswer:
    settings = get_settings()
    stats = GenerationStats()
    if not retrieved_sources:
        return GeneratedAnswer(
            answer=SupportChatbotAnswer(
                question_id=question_id,
                question=question,
                answer="I could not find enough matching support policy context in the synthetic knowledge base.",
                answer_status="no_answer",
                provider_used="fallback-unavailable",
                model_name="none",
                confidence=0,
                retrieval_confidence=0,
                missing_information=["No relevant source chunk was retrieved."],
            ),
            stats=stats,
        )

    should_try_ollama = ollama_client is not None or _ollama_available()
    if should_try_ollama:
        ollama_fn = lambda: ollama_client(question, retrieved_sources) if ollama_client else _ollama_generate(question, retrieved_sources)
        ollama_payload, timed_out = _call_with_timeout(ollama_fn, max(1, settings.local_model_timeout_seconds))
        if timed_out:
            stats.timeout_count += 1
            stats.warnings.append("Ollama Qwen timed out.")
        else:
            parsed = _coerce_payload(ollama_payload)
            if parsed:
                return GeneratedAnswer(
                    answer=_answer_from_payload(
                        payload=parsed,
                        question_id=question_id,
                        question=question,
                        retrieved_sources=retrieved_sources,
                        retrieval_confidence=retrieval_confidence,
                        provider_used="local-ollama",
                        model_name=settings.ollama_model,
                    ),
                    stats=stats,
                )
            stats.invalid_json_count += 1
            stats.warnings.append("Ollama Qwen did not return valid structured JSON.")
    else:
        stats.warnings.append("Ollama Qwen is unavailable; using GPT-4o fallback.")

    stats.fallback_count += 1
    openai_fn = lambda: openai_client(question, retrieved_sources) if openai_client else _openai_generate(question, retrieved_sources)
    openai_payload, openai_timed_out = _call_with_timeout(openai_fn, max(1, settings.local_model_timeout_seconds))
    if openai_timed_out:
        stats.timeout_count += 1
        stats.warnings.append("GPT-4o fallback timed out.")
    parsed_openai = _coerce_payload(openai_payload)
    if parsed_openai:
        openai_answer = _answer_from_payload(
            payload=parsed_openai,
            question_id=question_id,
            question=question,
            retrieved_sources=retrieved_sources,
            retrieval_confidence=retrieval_confidence,
            provider_used="gpt-4o-fallback",
            model_name=settings.openai_model,
        )
        openai_answer.warnings.extend(stats.warnings)
        return GeneratedAnswer(
            answer=openai_answer,
            stats=stats,
        )
    stats.invalid_json_count += 1
    stats.warnings.append("GPT-4o fallback was unavailable or did not return valid structured JSON.")
    return GeneratedAnswer(
        answer=_fallback_unavailable_answer(
            question_id=question_id,
            question=question,
            retrieved_sources=retrieved_sources,
            retrieval_confidence=retrieval_confidence,
            warnings=stats.warnings,
        ),
        stats=stats,
    )
