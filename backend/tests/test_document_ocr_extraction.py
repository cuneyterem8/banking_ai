from pathlib import Path
from typing import Any

from app.use_cases.document_ocr.data_generation import write_artifacts
from app.use_cases.document_ocr.extraction import _extract_document_inner, extract_documents
from app.use_cases.document_ocr.raw_data import load_ground_truth


def _fallback_from_ground_truth(document: dict[str, Any], _path: Path) -> dict[str, Any]:
    return {
        "fields": document["expected_fields"],
        "tables": document.get("expected_tables", []),
        "raw_text_excerpt": f"Synthetic fallback extraction for {document['document_id']}",
    }


def test_digital_bank_statement_extracts_expected_fields_and_rows() -> None:
    write_artifacts()
    ground_truth = load_ground_truth()
    statement = next(item for item in ground_truth["documents"] if item["document_type"] == "bank_statement")

    result = _extract_document_inner(statement, fallback_client=lambda _document, _path: None)

    assert result.extraction_status == "completed"
    assert result.provider_used == "local-ocr"
    assert result.confidence == 1
    assert result.fields["customer_id"] == "CUST-OCR-0001"
    assert result.fields["document_type"] == "Bank Statement"
    assert result.tables[0].name == "transactions"
    assert len(result.tables[0].rows) == 8
    assert result.validation_issues == []


def test_account_confirmation_and_income_proof_validate_locally() -> None:
    write_artifacts()
    ground_truth = load_ground_truth()
    documents = [
        next(item for item in ground_truth["documents"] if item["document_type"] == "account_confirmation"),
        next(item for item in ground_truth["documents"] if item["document_type"] == "income_proof"),
    ]

    results = [_extract_document_inner(document, fallback_client=lambda _document, _path: None) for document in documents]

    assert [item.extraction_status for item in results] == ["completed", "completed"]
    assert all(item.provider_used == "local-ocr" for item in results)
    assert all(item.confidence == 1 for item in results)
    assert results[0].fields["account_status"] == "Active"
    assert results[1].fields["employment_status"] == "Full-time"


def test_scanned_document_uses_structured_fallback() -> None:
    write_artifacts()
    ground_truth = load_ground_truth()
    scanned = next(item for item in ground_truth["documents"] if item["document_type"] == "scanned_statement")

    result = _extract_document_inner(scanned, fallback_client=_fallback_from_ground_truth)

    assert result.extraction_status == "fallback_completed"
    assert result.provider_used == "gpt-4o-fallback"
    assert result.confidence == 1
    assert result.fields["document_id"] == scanned["document_id"]
    assert len(result.tables[0].rows) == 8


def test_scanned_document_without_fallback_returns_clear_warning(monkeypatch) -> None:
    write_artifacts()
    ground_truth = load_ground_truth()
    scanned = next(item for item in ground_truth["documents"] if item["document_type"] == "transfer_notice")
    monkeypatch.setattr("app.use_cases.document_ocr.extraction._openai_fallback", lambda _document, _path: None)

    result = _extract_document_inner(scanned, fallback_client=None)

    assert result.extraction_status == "fallback_unavailable"
    assert result.provider_used == "fallback-unavailable"
    assert result.confidence == 0
    assert any("GPT-4o fallback unavailable" in issue for issue in result.validation_issues)


def test_extract_documents_summary_uses_mixed_provider_with_fallback() -> None:
    write_artifacts()
    ground_truth = load_ground_truth()
    subset_documents = [
        next(item for item in ground_truth["documents"] if item["document_type"] == "bank_statement"),
        next(item for item in ground_truth["documents"] if item["document_type"] == "scanned_statement"),
    ]
    subset = {
        "generation_seed": ground_truth["generation_seed"],
        "customer_count": 1,
        "document_count": len(subset_documents),
        "documents": subset_documents,
    }

    payload = extract_documents(subset, fallback_client=_fallback_from_ground_truth)

    assert payload.summary.document_count == 2
    assert payload.summary.provider_used == "mixed-local-gpt4o"
    assert payload.summary.fallback_count == 1
    assert payload.summary.field_accuracy == 1
    assert payload.summary.table_row_recall == 1
