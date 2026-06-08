from app.use_cases.email_automation import llm_service
from app.use_cases.email_automation.llm_service import generate_email_draft
from app.use_cases.email_automation.raw_data import load_evaluation_cases
from app.use_cases.email_automation.template_engine import render_email_case


def _payload(subject: str = "A compliant synthetic email") -> dict:
    return {
        "subject": subject,
        "preheader": "Review the synthetic update.",
        "body": "Hello, this synthetic message uses only masked customer context.",
        "call_to_action": "Review details",
        "tone_tags": ["clear", "professional"],
        "required_disclosures": ["This service message is not a marketing offer."],
        "personalization_used": ["first_name", "masked_account"],
        "confidence": 0.91,
    }


def test_email_llm_accepts_valid_ollama_json() -> None:
    case = load_evaluation_cases()[0]
    baseline = render_email_case(case)

    generated = generate_email_draft(case=case, baseline=baseline, ollama_client=lambda _case, _baseline: _payload())

    assert generated.draft.provider_used == "local-ollama"
    assert generated.draft.generation_status == "generated"
    assert generated.stats.fallback_count == 0
    assert generated.draft.subject == "A compliant synthetic email"


def test_email_llm_falls_back_to_gpt4o_on_invalid_ollama_json() -> None:
    case = load_evaluation_cases()[0]
    baseline = render_email_case(case)

    generated = generate_email_draft(
        case=case,
        baseline=baseline,
        ollama_client=lambda _case, _baseline: "not-json",
        openai_client=lambda _case, _baseline: _payload("GPT fallback draft"),
    )

    assert generated.draft.provider_used == "gpt-4o-fallback"
    assert generated.stats.fallback_count == 1
    assert generated.stats.invalid_json_count == 1
    assert generated.draft.subject == "GPT fallback draft"


def test_email_llm_returns_baseline_when_providers_are_unavailable(monkeypatch) -> None:
    case = load_evaluation_cases()[0]
    baseline = render_email_case(case)
    monkeypatch.setattr(llm_service, "_ollama_available", lambda: False)
    monkeypatch.setattr(llm_service, "_openai_generate", lambda _case, _baseline: None)

    generated = generate_email_draft(case=case, baseline=baseline)

    assert generated.draft.provider_used == "fallback-unavailable"
    assert generated.draft.generation_status == "fallback_unavailable"
    assert generated.stats.fallback_count == 1
    assert generated.stats.invalid_json_count == 1
