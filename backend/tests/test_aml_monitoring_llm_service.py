from app.use_cases.aml_monitoring.llm_service import draft_narrative
from app.use_cases.aml_monitoring.schemas import AmlAlertDecision


def _alert() -> AmlAlertDecision:
    return AmlAlertDecision(
        alert_id="AML-TEST-0001",
        customer_id="CUST-TEST",
        account_id="ACCT-TEST",
        typology_tag="Structuring",
        sar_probability=0.84,
        risk_level="Critical",
        predicted_sar_recommended=1,
        actual_sar_recommended=1,
        decision="Draft SAR",
        top_factors=["Multiple recent structuring-pattern events were detected."],
        related_entities=["ENT-TEST-1"],
        linked_transaction_count=14,
    )


def test_aml_valid_ollama_json_is_accepted() -> None:
    generated = draft_narrative(
        _alert(),
        ollama_client=lambda alert: {
            "narrative_status": "drafted",
            "alert_id": alert.alert_id,
            "summary": "Synthetic structuring pattern requires analyst review.",
            "suspicious_activity_type": "Structuring",
            "evidence_bullets": alert.top_factors,
            "recommended_next_steps": ["Review linked synthetic transactions."],
            "missing_information": [],
            "confidence": 0.81,
        },
        openai_client=lambda alert: None,
    )

    assert generated.narrative.provider_used == "local-ollama"
    assert generated.narrative.narrative_status == "drafted"
    assert generated.stats.fallback_count == 0


def test_aml_invalid_ollama_json_falls_back_to_gpt4o() -> None:
    generated = draft_narrative(
        _alert(),
        ollama_client=lambda alert: "not-json",
        openai_client=lambda alert: {
            "narrative_status": "drafted",
            "alert_id": alert.alert_id,
            "summary": "Fallback drafted a synthetic AML narrative.",
            "suspicious_activity_type": "Structuring",
            "evidence_bullets": alert.top_factors,
            "recommended_next_steps": ["Document analyst disposition."],
            "missing_information": [],
            "confidence": 0.74,
        },
    )

    assert generated.narrative.provider_used == "gpt-4o-fallback"
    assert generated.stats.fallback_count == 1
    assert generated.stats.invalid_json_count == 1


def test_aml_no_provider_returns_fallback_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("app.use_cases.aml_monitoring.llm_service._ollama_available", lambda: False)

    generated = draft_narrative(_alert(), openai_client=lambda alert: None)

    assert generated.narrative.provider_used == "fallback-unavailable"
    assert generated.narrative.narrative_status == "fallback_unavailable"
    assert generated.stats.fallback_count == 1
