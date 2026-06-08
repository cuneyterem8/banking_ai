from app.use_cases.support_chatbot.data_generation import GENERATION_SEED, support_data_root, write_artifacts
from app.use_cases.support_chatbot.raw_data import load_ground_truth, load_manifest


def test_support_chatbot_generation_layout_and_manifest() -> None:
    paths = write_artifacts()
    manifest = load_manifest()
    ground_truth = load_ground_truth()

    assert set(paths.keys()) == {"raw_root", "metadata", "ground_truth"}
    assert manifest["generation_seed"] == GENERATION_SEED
    assert manifest["knowledge_document_count"] == 8
    assert manifest["evaluation_question_count"] == 8
    assert manifest["chunk_count"] == ground_truth["chunk_count"]
    assert len(manifest["documents"]) == 8
    assert (support_data_root() / "raw" / "policies" / "card_dispute_policy.pdf").exists()
    assert (support_data_root() / "raw" / "faq" / "customer_support_faq.json").exists()
    assert (support_data_root() / "raw" / "evaluation" / "support_questions.json").exists()


def test_support_chatbot_generation_is_deterministic() -> None:
    write_artifacts()
    first = load_manifest()
    first_checksums = [item["checksum"] for item in first["documents"]]

    write_artifacts()
    second = load_manifest()
    second_checksums = [item["checksum"] for item in second["documents"]]

    assert first_checksums == second_checksums
    assert first["documents"][0]["relative_path"] == "raw/policies/retail_banking_policy.pdf"


def test_support_policy_pdf_contains_extractable_text() -> None:
    write_artifacts()
    pdf_path = support_data_root() / "raw" / "policies" / "card_dispute_policy.pdf"

    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Unauthorized card transaction intake" in text
    assert "provisional credit" in text
