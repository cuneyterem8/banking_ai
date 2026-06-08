from app.services.ml_job_queue import mark_api_ready, mark_startup_pipeline_complete
from app.services.ml_training_manager import (
    STARTUP_STAGES,
    _credit_state,
    _lock,
    _stage_states,
    _state,
    get_platform_readiness,
    get_startup_status,
    get_training_status,
)


EXPECTED_STARTUP_ORDER = [
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


def _set_stage(slug: str, *, status: str, stage: str = "idle", progress: int = 0) -> None:
    state = _stage_states[slug]
    state.status = status
    state.stage = stage
    state.progress_percent = progress
    state.training_run_id = None
    state.error = None


def test_startup_registry_contains_exact_implemented_order() -> None:
    assert [stage.slug for stage in STARTUP_STAGES] == EXPECTED_STARTUP_ORDER
    assert [stage.order for stage in STARTUP_STAGES] == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_api_ready_before_ml_training_finishes() -> None:
    mark_api_ready()
    with _lock:
        for slug in EXPECTED_STARTUP_ORDER:
            _set_stage(slug, status="idle")
        _set_stage("fraud-detection", status="running", stage="fitting", progress=27)
        _set_stage("credit-risk", status="queued", stage="queued")

    readiness = get_platform_readiness()
    assert readiness["ready"] is True
    assert readiness["ml_training_ready"] is False
    assert readiness["ml_phase"] == "fraud_training"
    assert readiness["total_stage_count"] == 9
    assert readiness["active_stage"]["use_case_slug"] == "fraud-detection"


def test_credit_stays_idle_until_fraud_pipeline_advances() -> None:
    with _lock:
        for slug in EXPECTED_STARTUP_ORDER:
            _set_stage(slug, status="idle")
        _state.status = "running"
        _state.stage = "fitting"
        _credit_state.status = "idle"
        _credit_state.stage = "idle"

    credit = get_training_status("credit-risk")
    fraud = get_training_status("fraud-detection")
    assert fraud["status"] == "running"
    assert credit["status"] == "idle"


def test_ml_training_ready_when_startup_finished() -> None:
    mark_api_ready()
    mark_startup_pipeline_complete()
    with _lock:
        for slug in EXPECTED_STARTUP_ORDER:
            _set_stage(slug, status="completed", stage="done", progress=100)

    readiness = get_platform_readiness()
    assert readiness["ready"] is True
    assert readiness["ml_training_ready"] is True
    assert readiness["ml_phase"] == "ready"


def test_training_status_supports_all_startup_stages() -> None:
    with _lock:
        for slug in EXPECTED_STARTUP_ORDER:
            _set_stage(slug, status="queued", stage="queued")

    statuses = [get_training_status(slug) for slug in EXPECTED_STARTUP_ORDER]
    assert [status["use_case_slug"] for status in statuses] == EXPECTED_STARTUP_ORDER
    assert [status["order"] for status in statuses] == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    startup = get_startup_status()
    assert startup["total_stage_count"] == 9
    assert [stage["use_case_slug"] for stage in startup["stages"]] == EXPECTED_STARTUP_ORDER
