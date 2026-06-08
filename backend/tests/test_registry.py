from app.use_cases.registry import USE_CASES, get_use_case


def test_registry_contains_ten_use_cases() -> None:
    assert len(USE_CASES) == 10
    assert [item.implementation_order for item in USE_CASES] == list(range(1, 11))


def test_stage_nine_use_cases_are_implemented() -> None:
    implemented = [item.slug for item in USE_CASES if item.status == "implemented"]
    assert implemented == [
        "fraud-detection",
        "credit-risk",
        "document-ocr",
        "support-chatbot",
        "liquidity-forecast",
        "aml-monitoring",
        "kyc-kyb",
        "email-automation",
        "market-intelligence",
    ]
    assert get_use_case("fraud-detection") is not None
    assert get_use_case("credit-risk") is not None
    assert get_use_case("document-ocr") is not None
    assert get_use_case("support-chatbot") is not None
    assert get_use_case("liquidity-forecast") is not None
    assert get_use_case("aml-monitoring") is not None
    assert get_use_case("kyc-kyb") is not None
    assert get_use_case("email-automation") is not None
    assert get_use_case("market-intelligence") is not None
