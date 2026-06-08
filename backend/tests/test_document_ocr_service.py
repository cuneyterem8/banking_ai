from sqlmodel import Session

from app.api.use_cases import get_raw_data
from app.db.models import ModelRun, ProcessedResult, UseCase
from app.services.seeding import seed_document_ocr
from app.use_cases.document_ocr.service import DOCUMENT_OCR_RESULT_TYPE, get_document_ocr_latest
from app.use_cases.registry import get_use_case


def _ensure_document_use_case(session: Session) -> None:
    item = get_use_case("document-ocr")
    assert item is not None
    session.merge(
        UseCase(
            slug=item.slug,
            title=item.title,
            category=item.category,
            description=item.description,
            adapter_type=item.adapter_type,
            model_family=item.model_family,
            status=item.status,
            implementation_order=item.implementation_order,
        )
    )
    session.commit()


def test_seed_document_ocr_raw_api_payload(session: Session) -> None:
    _ensure_document_use_case(session)
    seed_document_ocr(session)

    payload = get_raw_data("document-ocr", session)

    assert len(payload["datasets"]) == 1
    assert payload["datasets"][0]["dataset_key"] == "manifest"
    assert payload["datasets"][0]["payload"]["document_count"] == 60
    assert payload["datasets"][0]["payload"]["customer_count"] == 12
    assert len(payload["datasets"][0]["payload"]["preview"]) == 12
    assert len(payload["artifacts"]) == 62


def test_get_document_ocr_latest_returns_persisted_result(session: Session) -> None:
    _ensure_document_use_case(session)
    run = ModelRun(
        use_case_slug="document-ocr",
        adapter_type="ocr-local-gpt4o-fallback",
        provider_used="mixed-local-gpt4o",
        model_name="pdfplumber/PyMuPDF + gpt-4o",
        status="completed",
        metrics={"document_count": 2},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        ProcessedResult(
            run_id=run.id,
            use_case_slug="document-ocr",
            result_type=DOCUMENT_OCR_RESULT_TYPE,
            payload={
                "summary": {"document_count": 2, "provider_used": "mixed-local-gpt4o"},
                "documents": [],
            },
            explanation={},
        )
    )
    session.commit()

    payload = get_document_ocr_latest(session)

    assert payload["latest"] is not None
    assert payload["latest"]["run"]["id"] == run.id
    assert payload["latest"]["payload"]["summary"]["provider_used"] == "mixed-local-gpt4o"
