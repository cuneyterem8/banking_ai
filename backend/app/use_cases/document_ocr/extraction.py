import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any, Callable

from app.config import get_settings
from app.use_cases.document_ocr.data_generation import document_data_root
from app.use_cases.document_ocr.schemas import DocumentExtraction, DocumentOcrPayload, DocumentOcrSummary, OcrTable

FallbackClient = Callable[[dict[str, Any], Path], dict[str, Any] | None]

LABEL_MAP = {
    "Document ID": "document_id",
    "Document Type": "document_type",
    "Customer ID": "customer_id",
    "Customer Name": "customer_name",
    "Masked Account Number": "masked_account_number",
    "Statement Period": "statement_period",
    "Opening Balance": "opening_balance",
    "Closing Balance": "closing_balance",
    "Currency": "currency",
    "IBAN": "iban",
    "Branch": "branch",
    "Issue Date": "issue_date",
    "Account Open Date": "account_open_date",
    "Account Status": "account_status",
    "Employer": "employer",
    "Employment Status": "employment_status",
    "Monthly Gross Income": "monthly_gross_income",
    "Monthly Net Income": "monthly_net_income",
    "Payroll Date": "payroll_date",
    "Transfer Date": "transfer_date",
    "Transfer Amount": "transfer_amount",
    "Transfer Status": "transfer_status",
}

TRANSACTION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*\|")


def _extract_text_pdfplumber(path: Path) -> str:
    try:
        import pdfplumber
    except ModuleNotFoundError:
        return ""
    try:
        text_parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(part for part in text_parts if part)
    except Exception:
        return ""


def _extract_text_pymupdf(path: Path) -> str:
    try:
        import fitz
    except ModuleNotFoundError:
        return ""
    try:
        text_parts: list[str] = []
        with fitz.open(path) as doc:
            for page in doc:
                text_parts.append(page.get_text("text") or "")
        return "\n".join(part for part in text_parts if part)
    except Exception:
        return ""


def _local_text(path: Path) -> tuple[str, str]:
    if path.suffix.lower() != ".pdf":
        return "", "local-ocr"
    text = _extract_text_pdfplumber(path)
    if len(text.strip()) >= 80:
        return text, "local-ocr"
    fallback_text = _extract_text_pymupdf(path)
    return fallback_text, "local-ocr"


def _parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        key = LABEL_MAP.get(label.strip())
        if key and value.strip():
            fields[key] = value.strip()
    return fields


def _parse_transaction_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not TRANSACTION_RE.match(line.strip()):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 5:
            continue
        rows.append(
            {
                "date": parts[0],
                "description": parts[1],
                "type": parts[2],
                "amount": parts[3],
                "balance": parts[4],
            }
        )
    return rows


def _normalize(value: Any) -> str:
    return str(value).strip().lower()


def _validate_fields(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[int, list[str]]:
    matched = 0
    issues: list[str] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value is None:
            issues.append(f"Missing field: {key}")
        elif _normalize(actual_value) == _normalize(expected_value):
            matched += 1
        else:
            issues.append(f"Mismatch for {key}: expected {expected_value}, got {actual_value}")
    return matched, issues


def _validate_tables(expected_tables: list[dict[str, Any]], tables: list[OcrTable]) -> tuple[int, int]:
    expected_rows = [
        row
        for table in expected_tables
        for row in table.get("rows", [])
    ]
    actual_rows = [
        row
        for table in tables
        for row in table.rows
    ]
    if not expected_rows:
        return 0, 0
    matched = 0
    for expected in expected_rows:
        if any(all(_normalize(actual.get(key)) == _normalize(value) for key, value in expected.items()) for actual in actual_rows):
            matched += 1
    return matched, len(expected_rows)


def _image_payload_for_fallback(path: Path) -> tuple[str, str] | None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        data = path.read_bytes()
        return "image/jpeg", base64.b64encode(data).decode("ascii")
    if suffix == ".pdf":
        try:
            import fitz
        except ModuleNotFoundError:
            return None
        try:
            with fitz.open(path) as doc:
                page = doc[0]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                return "image/png", base64.b64encode(pixmap.tobytes("png")).decode("ascii")
        except Exception:
            return None
    return None


def _openai_fallback(document: dict[str, Any], path: Path) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    image_payload = _image_payload_for_fallback(path)
    if image_payload is None:
        return None
    mime_type, image_base64 = image_payload
    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        return None

    schema_hint = {
        "fields": {key: "string" for key in document["expected_fields"]},
        "tables": [
            {
                "name": table["name"],
                "row_count_hint": len(table.get("rows", [])),
                "columns": list(table.get("rows", [{}])[0].keys()) if table.get("rows") else [],
            }
            for table in document.get("expected_tables", [])
        ],
    }
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.local_model_timeout_seconds)
    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Extract the banking document into strict JSON. Return only keys: fields, tables, raw_text_excerpt.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "This is synthetic MVP data. Extract visible fields and tables. "
                            "For bank statements, return every transaction row with date, description, type, amount, and balance. "
                            f"Document type: {document['document_type']}. Expected JSON shape: {json.dumps(schema_hint)}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                    },
                ],
            },
        ],
        temperature=0,
    )
    content = response.choices[0].message.content
    if not content:
        return None
    return json.loads(content)


def _fallback_extract(document: dict[str, Any], path: Path, fallback_client: FallbackClient | None) -> dict[str, Any] | None:
    if fallback_client is not None:
        return fallback_client(document, path)
    try:
        return _openai_fallback(document, path)
    except Exception:
        return None


def _coerce_tables(raw_tables: Any) -> list[OcrTable]:
    tables: list[OcrTable] = []
    if not isinstance(raw_tables, list):
        return tables
    for index, table in enumerate(raw_tables):
        if not isinstance(table, dict):
            continue
        name = str(table.get("name") or f"table_{index + 1}")
        rows = table.get("rows") if isinstance(table.get("rows"), list) else []
        tables.append(OcrTable(name=name, rows=[row for row in rows if isinstance(row, dict)]))
    return tables


def _extract_document_inner(
    document: dict[str, Any],
    *,
    fallback_client: FallbackClient | None = None,
) -> DocumentExtraction:
    path = document_data_root() / document["relative_path"]
    expected_fields = document["expected_fields"]
    expected_tables = document.get("expected_tables", [])
    text, provider_used = _local_text(path)
    fields = _parse_fields(text)
    tables = [OcrTable(name="transactions", rows=_parse_transaction_rows(text))] if _parse_transaction_rows(text) else []
    status = "completed"

    needs_fallback = document.get("is_scanned") or len(text.strip()) < 80 or len(fields) < max(2, len(expected_fields) // 2)
    if needs_fallback:
        fallback_payload = _fallback_extract(document, path, fallback_client)
        if fallback_payload:
            provider_used = "gpt-4o-fallback"
            status = "fallback_completed"
            fields = fallback_payload.get("fields", {}) if isinstance(fallback_payload.get("fields"), dict) else {}
            tables = _coerce_tables(fallback_payload.get("tables"))
            text = str(fallback_payload.get("raw_text_excerpt") or "")
        else:
            provider_used = "fallback-unavailable"
            status = "fallback_unavailable"
            fields = {}
            tables = []

    matched_fields, issues = _validate_fields(expected_fields, fields)
    matched_rows, expected_rows = _validate_tables(expected_tables, tables)
    if status == "fallback_unavailable":
        issues.append("GPT-4o fallback unavailable for image-only or low-confidence document.")
    if expected_rows and matched_rows < expected_rows:
        issues.append(f"Table row recall incomplete: {matched_rows}/{expected_rows}")
    field_score = matched_fields / len(expected_fields) if expected_fields else 1.0
    table_score = matched_rows / expected_rows if expected_rows else 1.0
    confidence = round((field_score * 0.75) + (table_score * 0.25), 4)
    if status == "fallback_unavailable":
        confidence = 0
    return DocumentExtraction(
        document_id=document["document_id"],
        customer_id=document["customer_id"],
        document_type=document["document_type"],
        file_name=document["file_name"],
        provider_used=provider_used,
        extraction_status=status,
        confidence=confidence,
        fields=fields,
        tables=tables,
        validation_issues=issues[:10],
        raw_text_excerpt=" ".join(text.split())[:500],
    )


def _timeout_document(document: dict[str, Any]) -> DocumentExtraction:
    return DocumentExtraction(
        document_id=document["document_id"],
        customer_id=document["customer_id"],
        document_type=document["document_type"],
        file_name=document["file_name"],
        provider_used="timeout",
        extraction_status="timeout",
        confidence=0,
        fields={},
        tables=[],
        validation_issues=["Document extraction exceeded LOCAL_MODEL_TIMEOUT_SECONDS."],
        raw_text_excerpt="",
    )


def _run_with_timeout(
    document: dict[str, Any],
    timeout_seconds: int,
    fallback_client: FallbackClient | None,
) -> DocumentExtraction:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_extract_document_inner, document, fallback_client=fallback_client)
    try:
        result = future.result(timeout=timeout_seconds)
        executor.shutdown(wait=False, cancel_futures=False)
        return result
    except TimeoutError:
        executor.shutdown(wait=False, cancel_futures=True)
        return _timeout_document(document)


def extract_documents(
    ground_truth: dict[str, Any],
    *,
    fallback_client: FallbackClient | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> DocumentOcrPayload:
    settings = get_settings()
    documents = ground_truth["documents"]
    extracted: list[DocumentExtraction] = []
    for index, document in enumerate(documents, start=1):
        if progress_callback:
            progress_callback(5 + int((index - 1) / max(len(documents), 1) * 80), f"extracting_{document['document_id'].lower()}")
        extracted.append(
            _run_with_timeout(
                document,
                max(1, int(settings.local_model_timeout_seconds)),
                fallback_client,
            )
        )

    total_expected_fields = sum(len(item["expected_fields"]) for item in documents)
    total_matched_fields = 0
    expected_table_rows = 0
    matched_table_rows = 0
    expected_by_id = {item["document_id"]: item for item in documents}
    for item in extracted:
        expected = expected_by_id[item.document_id]
        matched, _ = _validate_fields(expected["expected_fields"], item.fields)
        total_matched_fields += matched
        table_matched, table_expected = _validate_tables(expected.get("expected_tables", []), item.tables)
        matched_table_rows += table_matched
        expected_table_rows += table_expected

    fallback_count = sum(1 for item in extracted if item.extraction_status in {"fallback_completed", "fallback_unavailable"})
    timeout_count = sum(1 for item in extracted if item.extraction_status == "timeout")
    warning_count = sum(len(item.validation_issues) for item in extracted)
    provider_used = "local-ocr"
    if any(item.provider_used == "gpt-4o-fallback" for item in extracted):
        provider_used = "mixed-local-gpt4o" if any(item.provider_used == "local-ocr" for item in extracted) else "gpt-4o-fallback"

    summary = DocumentOcrSummary(
        document_count=len(extracted),
        customer_count=ground_truth["customer_count"],
        extracted_field_count=sum(len(item.fields) for item in extracted),
        expected_field_count=total_expected_fields,
        field_accuracy=round(total_matched_fields / total_expected_fields, 4) if total_expected_fields else 1.0,
        table_row_recall=round(matched_table_rows / expected_table_rows, 4) if expected_table_rows else 1.0,
        average_confidence=round(sum(item.confidence for item in extracted) / len(extracted), 4) if extracted else 0.0,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        warning_count=warning_count,
        provider_used=provider_used,
    )
    if progress_callback:
        progress_callback(90, "saving_results")
    return DocumentOcrPayload(summary=summary, documents=extracted)
