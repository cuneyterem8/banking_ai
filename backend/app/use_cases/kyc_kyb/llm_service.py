from __future__ import annotations

import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.config import get_settings
from app.use_cases.kyc_kyb.schemas import KycKybDocumentManifest

ImageFallbackClient = Callable[[KycKybDocumentManifest, Path], dict[str, Any] | str | None]


@dataclass
class ImageExtractionResult:
    fields: dict[str, Any]
    provider_used: str
    status: str
    raw_text_excerpt: str
    warnings: list[str] = field(default_factory=list)
    fallback_count: int = 0
    timeout_count: int = 0
    invalid_json_count: int = 0


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


def _openai_image_extract(document: KycKybDocumentManifest, path: Path) -> dict[str, Any] | str | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        return None
    image_base64 = base64.b64encode(path.read_bytes()).decode("ascii")
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.local_model_timeout_seconds)
    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Extract the synthetic KYC/KYB image document into strict JSON."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "This is synthetic MVP data. Return JSON with keys: fields, raw_text_excerpt. "
                            f"Document type: {document.document_type}. Expected field names: {json.dumps(list(document.expected_fields))}"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                ],
            },
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def extract_image_fields(
    document: KycKybDocumentManifest,
    path: Path,
    *,
    fallback_client: ImageFallbackClient | None = None,
) -> ImageExtractionResult:
    if document.local_fields_hint:
        excerpt = " ".join(f"{key}: {value}" for key, value in document.local_fields_hint.items())
        return ImageExtractionResult(
            fields=dict(document.local_fields_hint),
            provider_used="local-image-metadata",
            status="completed",
            raw_text_excerpt=excerpt[:500],
        )
    settings = get_settings()
    call = lambda: fallback_client(document, path) if fallback_client else _openai_image_extract(document, path)
    payload, timed_out = _call_with_timeout(call, max(1, settings.local_model_timeout_seconds))
    warnings: list[str] = []
    if timed_out:
        warnings.append("GPT-4o image extraction timed out.")
    parsed = _coerce_payload(payload)
    if parsed and isinstance(parsed.get("fields"), dict):
        return ImageExtractionResult(
            fields=parsed["fields"],
            provider_used="gpt-4o-fallback",
            status="fallback_completed",
            raw_text_excerpt=str(parsed.get("raw_text_excerpt") or "")[:500],
            warnings=warnings,
            fallback_count=1,
            timeout_count=1 if timed_out else 0,
        )
    warnings.append("GPT-4o fallback was unavailable or did not return valid KYC/KYB image JSON.")
    return ImageExtractionResult(
        fields={},
        provider_used="fallback-unavailable",
        status="fallback_unavailable",
        raw_text_excerpt="",
        warnings=warnings,
        fallback_count=1,
        timeout_count=1 if timed_out else 0,
        invalid_json_count=0 if payload is None else 1,
    )
