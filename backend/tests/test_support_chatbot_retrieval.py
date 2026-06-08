from app.use_cases.support_chatbot.data_generation import write_artifacts
from app.use_cases.support_chatbot.raw_data import load_evaluation_cases, load_manifest
from app.use_cases.support_chatbot.retrieval import build_knowledge_chunks, retrieve_chunks


def test_support_chatbot_chunks_are_stable_and_match_manifest_count() -> None:
    write_artifacts()
    manifest = load_manifest()
    chunks = build_knowledge_chunks()

    assert len(chunks) == manifest["chunk_count"]
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    faq_chunks = [chunk for chunk in chunks if chunk.source_id == "SUPPORT-FAQ"]
    assert len(faq_chunks) == 5
    assert all("FAQ:" in chunk.text and "Answer:" in chunk.text for chunk in faq_chunks)


def test_bm25_retrieval_returns_expected_sources_for_ground_truth_questions() -> None:
    write_artifacts()
    chunks = build_knowledge_chunks()

    for case in load_evaluation_cases():
        sources, _all_chunks, confidence, no_answer = retrieve_chunks(case.question, chunks=chunks)
        source_ids = {source.source_id for source in sources}
        assert no_answer is False
        assert confidence > 0
        assert source_ids.intersection(case.expected_source_ids)
