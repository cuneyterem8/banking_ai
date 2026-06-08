from app.use_cases.document_ocr.data_generation import CUSTOMER_COUNT, GENERATION_SEED, document_data_root, write_artifacts
from app.use_cases.document_ocr.raw_data import load_ground_truth, load_manifest


def test_document_ocr_generation_layout_and_manifest() -> None:
    paths = write_artifacts()
    manifest = load_manifest()
    ground_truth = load_ground_truth()

    assert set(paths.keys()) == {"raw_root", "metadata", "ground_truth"}
    assert manifest["generation_seed"] == GENERATION_SEED
    assert manifest["customer_count"] == CUSTOMER_COUNT
    assert manifest["document_count"] == CUSTOMER_COUNT * 5
    assert ground_truth["document_count"] == manifest["document_count"]
    assert len(list((document_data_root() / "raw").glob("customer_*"))) == CUSTOMER_COUNT

    first_customer_files = sorted((document_data_root() / "raw" / "customer_0001").iterdir())
    assert [path.name for path in first_customer_files] == [
        "account_confirmation.pdf",
        "bank_statement.pdf",
        "income_proof.pdf",
        "scanned_statement.pdf",
        "transfer_notice.jpg",
    ]


def test_document_ocr_generation_is_deterministic() -> None:
    write_artifacts()
    first_manifest = load_manifest()
    first_checksums = [item["sha256"] for item in first_manifest["documents"]]

    write_artifacts()
    second_manifest = load_manifest()
    second_checksums = [item["sha256"] for item in second_manifest["documents"]]

    assert first_checksums == second_checksums
    assert first_manifest["documents"][0]["relative_path"] == "raw/customer_0001/bank_statement.pdf"


def test_digital_document_contains_extractable_text() -> None:
    write_artifacts()
    ground_truth = load_ground_truth()
    statement = next(item for item in ground_truth["documents"] if item["document_type"] == "bank_statement")
    pdf_path = document_data_root() / statement["relative_path"]

    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Synthetic Bank Statement" in text
    assert "Customer ID: CUST-OCR-0001" in text
    assert "Transaction Date | Description | Type | Amount | Balance" in text
