from pathlib import Path

from app.use_cases.kyc_kyb.llm_service import extract_image_fields
from app.use_cases.kyc_kyb.schemas import KycKybDocumentManifest


def _image_document(*, hint: dict | None = None) -> KycKybDocumentManifest:
    return KycKybDocumentManifest(
        document_id="KYC-TEST-ID-FRONT",
        package_id="KYC-TEST-0001",
        subject_type="individual",
        document_type="id_document_front",
        file_name="id_document_front.jpg",
        relative_path="raw/individuals/customer_0001/id_document_front.jpg",
        is_image=True,
        expected_fields={"Full Name": "Synthetic Customer Test", "Expiry Date": "2031-04-15"},
        local_fields_hint=hint or {},
    )


def test_kyc_kyb_local_image_hint_is_used_without_fallback(tmp_path: Path) -> None:
    document = _image_document(hint={"Full Name": "Synthetic Customer Test", "Expiry Date": "2031-04-15"})
    result = extract_image_fields(document, tmp_path / "id.jpg", fallback_client=lambda doc, path: None)

    assert result.provider_used == "local-image-metadata"
    assert result.status == "completed"
    assert result.fallback_count == 0
    assert result.fields["Full Name"] == "Synthetic Customer Test"


def test_kyc_kyb_mocked_gpt4o_image_fallback_is_accepted(tmp_path: Path) -> None:
    document = _image_document()
    result = extract_image_fields(
        document,
        tmp_path / "id.jpg",
        fallback_client=lambda doc, path: {
            "fields": {"Full Name": "Synthetic Customer Test", "Expiry Date": "2031-04-15"},
            "raw_text_excerpt": "Full Name: Synthetic Customer Test Expiry Date: 2031-04-15",
        },
    )

    assert result.provider_used == "gpt-4o-fallback"
    assert result.status == "fallback_completed"
    assert result.fallback_count == 1
    assert result.fields["Expiry Date"] == "2031-04-15"


def test_kyc_kyb_missing_image_fallback_returns_clear_warning(tmp_path: Path) -> None:
    document = _image_document()
    result = extract_image_fields(document, tmp_path / "id.jpg", fallback_client=lambda doc, path: None)

    assert result.provider_used == "fallback-unavailable"
    assert result.status == "fallback_unavailable"
    assert result.fallback_count == 1
    assert result.warnings
