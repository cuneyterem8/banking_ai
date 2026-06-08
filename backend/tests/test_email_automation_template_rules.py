from app.use_cases.email_automation.raw_data import load_campaigns, load_customers, load_evaluation_cases, load_events, load_templates
from app.use_cases.email_automation.rules import evaluate_compliance
from app.use_cases.email_automation.template_engine import render_email_case


def test_template_engine_fills_placeholders_without_sensitive_identifier_leakage() -> None:
    case = load_evaluation_cases()[0]
    draft = render_email_case(
        case,
        customers=load_customers(),
        events=load_events(),
        campaigns=load_campaigns(),
        templates=load_templates(),
    )

    assert "${" not in draft.subject
    assert "${" not in draft.body
    assert "ACCT-" not in draft.body
    assert draft.customer_id == case.customer_id
    assert draft.call_to_action


def test_compliance_rules_detect_common_email_policy_failures() -> None:
    campaign_case = next(case for case in load_evaluation_cases() if case.communication_type == "campaign")
    baseline = render_email_case(
        campaign_case,
        customers=load_customers(),
        events=load_events(),
        campaigns=load_campaigns(),
        templates=load_templates(),
    )
    broken = baseline.model_copy(
        update={
            "subject": "Guaranteed 9.99% return for your full account ACCT-12345678",
            "body": "Guaranteed approval with no risk. Full account ACCT-12345678 is eligible today.",
            "call_to_action": "",
            "required_disclosures": [],
        }
    )

    checked, findings = evaluate_compliance(broken)
    failed_rules = {finding.rule_id for finding in findings if finding.status == "failed"}

    assert checked.compliance_status == "Rejected"
    assert checked.risk_level in {"High", "Critical"}
    assert {
        "no_full_identifier",
        "no_misleading_claim",
        "has_call_to_action",
        "required_disclosure_present",
        "marketing_opt_out",
    }.issubset(failed_rules)
