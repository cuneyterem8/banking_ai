from pathlib import Path

from app.use_cases.email_automation.data_generation import write_artifacts
from app.use_cases.email_automation.raw_data import (
    load_campaigns,
    load_customers,
    load_evaluation_cases,
    load_events,
    load_ground_truth,
    load_manifest,
    load_templates,
    raw_artifact_paths,
)


def test_email_automation_data_generation_creates_expected_artifacts() -> None:
    paths = write_artifacts()
    manifest = load_manifest()
    ground_truth = load_ground_truth()

    assert all(Path(path).exists() for path in paths.values())

    assert manifest["customer_count"] == 120
    assert manifest["service_event_count"] == 80
    assert manifest["campaign_audience_count"] == 40
    assert manifest["evaluation_case_count"] == 24
    assert set(ground_truth["required_rule_ids"]) == {
        "no_full_identifier",
        "no_misleading_claim",
        "has_call_to_action",
        "required_disclosure_present",
        "marketing_opt_out",
    }

    assert len(load_customers()) == 120
    assert len(load_events()) == 80
    assert len(load_campaigns()) == 40
    assert len(load_templates()) >= 10
    assert len(load_evaluation_cases()) == 24
    assert len(raw_artifact_paths()) == 10
