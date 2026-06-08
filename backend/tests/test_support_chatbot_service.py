from typing import Any

from sqlmodel import Session

from app.api.use_cases import get_raw_data
from app.db.models import ModelRun, ProcessedResult, UseCase
from app.services.seeding import seed_support_chatbot
from app.use_cases.registry import get_use_case
from app.use_cases.support_chatbot.llm_service import GeneratedAnswer, GenerationStats, answer_question
from app.use_cases.support_chatbot.raw_data import load_evaluation_cases
from app.use_cases.support_chatbot.retrieval import build_knowledge_chunks, retrieve_chunks
from app.use_cases.support_chatbot.schemas import SupportChatRequest, SupportChatbotAnswer
from app.use_cases.support_chatbot.service import (
    SUPPORT_CHAT_RESULT_TYPE,
    SUPPORT_EVAL_RESULT_TYPE,
    chat_support_question,
    get_support_chatbot_latest,
    run_support_questions,
)


def _ensure_support_use_case(session: Session) -> None:
    item = get_use_case("support-chatbot")
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


def _strict_answer(_question: str, sources: list[Any]) -> dict[str, Any]:
    return {
        "answer": "Verify identity, follow the cited support policy, and document the next action.",
        "confidence": 0.92,
        "sources": [source.model_dump() for source in sources[:2]],
        "escalation_required": False,
        "escalation_reason": None,
        "policy_tags": ["support"],
        "missing_information": [],
    }


def test_seed_support_chatbot_raw_api_payload(session: Session) -> None:
    _ensure_support_use_case(session)
    seed_support_chatbot(session)

    payload = get_raw_data("support-chatbot", session)

    assert len(payload["datasets"]) == 1
    assert payload["datasets"][0]["dataset_key"] == "knowledge_base"
    assert payload["datasets"][0]["payload"]["knowledge_document_count"] == 8
    assert payload["datasets"][0]["payload"]["evaluation_question_count"] == 8
    assert payload["datasets"][0]["payload"]["chunk_count"] == 26
    assert len(payload["artifacts"]) == 11


def test_invalid_ollama_json_triggers_gpt4o_fallback() -> None:
    chunks = build_knowledge_chunks()
    sources, _all_chunks, confidence, _no_answer = retrieve_chunks(
        "What should an agent do when a customer reports an unauthorized card transaction?",
        chunks=chunks,
    )

    generated = answer_question(
        question="What should an agent do when a customer reports an unauthorized card transaction?",
        question_id="SUP-Q-001",
        retrieved_sources=sources,
        retrieval_confidence=confidence,
        ollama_client=lambda _question, _sources: "not json",
        openai_client=_strict_answer,
    )

    assert generated.answer.provider_used == "gpt-4o-fallback"
    assert generated.stats.fallback_count == 1
    assert generated.stats.invalid_json_count == 1
    assert generated.answer.sources


def test_missing_providers_returns_fallback_unavailable() -> None:
    chunks = build_knowledge_chunks()
    sources, _all_chunks, confidence, _no_answer = retrieve_chunks("How do I reverse a fee?", chunks=chunks)

    generated = answer_question(
        question="How do I reverse a fee?",
        question_id=None,
        retrieved_sources=sources,
        retrieval_confidence=confidence,
        ollama_client=lambda _question, _sources: None,
        openai_client=lambda _question, _sources: None,
    )

    assert generated.answer.answer_status == "fallback_unavailable"
    assert generated.answer.provider_used == "fallback-unavailable"
    assert generated.stats.fallback_count == 1


def test_run_support_questions_with_mock_llm_returns_metrics() -> None:
    cases = load_evaluation_cases()[:3]

    payload = run_support_questions(cases, ollama_client=_strict_answer)

    assert payload.summary.question_count == 3
    assert payload.summary.answered_count == 3
    assert payload.summary.provider_used == "local-ollama"
    assert payload.summary.source_recall > 0
    assert payload.answers[0].sources


def test_get_support_chatbot_latest_returns_eval_and_chat(session: Session) -> None:
    _ensure_support_use_case(session)
    eval_run = ModelRun(
        use_case_slug="support-chatbot",
        adapter_type="ollama-qwen-gpt4o-fallback",
        provider_used="local-ollama",
        model_name="qwen2.5:7b",
        status="completed",
        metrics={"question_count": 1},
    )
    chat_run = ModelRun(
        use_case_slug="support-chatbot",
        adapter_type="ollama-qwen-gpt4o-fallback",
        provider_used="gpt-4o-fallback",
        model_name="gpt-4o",
        status="completed",
        metrics={"question_count": 1},
    )
    session.add(eval_run)
    session.add(chat_run)
    session.commit()
    session.refresh(eval_run)
    session.refresh(chat_run)
    payload = {"summary": {"question_count": 1, "provider_used": "local-ollama"}, "answers": [], "retrieved_chunks": []}
    session.add(ProcessedResult(run_id=eval_run.id, use_case_slug="support-chatbot", result_type=SUPPORT_EVAL_RESULT_TYPE, payload=payload, explanation={}))
    session.add(ProcessedResult(run_id=chat_run.id, use_case_slug="support-chatbot", result_type=SUPPORT_CHAT_RESULT_TYPE, payload=payload, explanation={}))
    session.commit()

    latest = get_support_chatbot_latest(session)

    assert latest["latest"]["run"]["id"] == eval_run.id
    assert latest["latest_chat"]["run"]["id"] == chat_run.id


def test_chat_support_question_persists_single_answer(session: Session, monkeypatch) -> None:
    _ensure_support_use_case(session)
    seed_support_chatbot(session)

    def fake_answer_question(**kwargs: Any) -> GeneratedAnswer:
        return GeneratedAnswer(
            answer=SupportChatbotAnswer(
                question=kwargs["question"],
                answer="Use the card dispute policy.",
                answer_status="answered",
                provider_used="local-ollama",
                model_name="qwen2.5:7b",
                confidence=0.9,
                retrieval_confidence=kwargs["retrieval_confidence"],
                sources=kwargs["retrieved_sources"][:1],
            ),
            stats=GenerationStats(),
        )

    monkeypatch.setattr("app.use_cases.support_chatbot.service.answer_question", fake_answer_question)

    response = chat_support_question(
        session,
        SupportChatRequest(question="What should an agent do when a customer reports an unauthorized card transaction?"),
    )

    assert response["run"]["status"] == "completed"
    assert response["payload"]["answers"][0]["answer_status"] == "answered"
    assert response["result"]["result_type"] == SUPPORT_CHAT_RESULT_TYPE
