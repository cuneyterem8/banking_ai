from __future__ import annotations

from string import Template
from typing import Any

from app.use_cases.email_automation.raw_data import load_campaigns, load_customers, load_events, load_templates
from app.use_cases.email_automation.schemas import (
    CampaignRecord,
    CustomerEvent,
    CustomerProfile,
    EmailAutomationDraft,
    EmailGenerationCase,
    EmailTemplate,
)


def _index_by(items: list[Any], key: str) -> dict[str, Any]:
    return {str(getattr(item, key)): item for item in items}


def _event_label(event_type: str | None) -> str:
    return str(event_type or "service update").replace("_", " ")


def _service_detail(event: CustomerEvent | None) -> str:
    if event is None:
        return "Please review the latest service information in online banking."
    if event.event_type == "failed_payment":
        return f"A payment of ${event.amount_due:.2f} is due by {event.due_date}."
    if event.event_type == "loan_payment_reminder":
        return f"Your upcoming loan payment is due by {event.due_date}."
    if event.event_type == "branch_appointment_reminder":
        appointment = event.context.get("appointment_time") or "your scheduled time"
        return f"Your appointment at {event.branch_name} is scheduled for {appointment}."
    if event.event_type == "suspicious_login_notice":
        return "We noticed a synthetic login event and recommend reviewing recent account activity."
    if event.event_type == "kyc_refresh_reminder":
        return "Please review your profile information and complete any requested refresh steps."
    if event.event_type == "overdraft_warning":
        return "Your balance may need attention to avoid additional account impact."
    if event.event_type == "statement_ready":
        return "Your latest statement is ready in secure online banking."
    return "Your replacement card information is available in secure online banking."


def _render(value: str, context: dict[str, Any]) -> str:
    return Template(value).safe_substitute({key: "" if val is None else val for key, val in context.items()})


def render_email_case(
    case: EmailGenerationCase,
    *,
    customers: list[CustomerProfile] | None = None,
    events: list[CustomerEvent] | None = None,
    campaigns: list[CampaignRecord] | None = None,
    templates: list[EmailTemplate] | None = None,
) -> EmailAutomationDraft:
    customers_by_id = _index_by(customers or load_customers(), "customer_id")
    events_by_id = _index_by(events or load_events(), "event_id")
    campaigns_by_audience = _index_by(campaigns or load_campaigns(), "audience_id")
    templates_by_key = _index_by(templates or load_templates(), "template_key")

    customer = customers_by_id[case.customer_id]
    event = events_by_id.get(case.event_id or "")
    campaign = campaigns_by_audience.get(case.audience_id or "")
    template = templates_by_key[case.template_key]
    context = {
        "first_name": customer.first_name,
        "segment": customer.segment,
        "masked_account": event.masked_account if event else customer.masked_account,
        "product_name": event.product_name if event else "Synthetic Banking",
        "event_label": _event_label(case.event_type),
        "service_detail": _service_detail(event),
        "support_phone": "1-800-000-0101",
        "campaign_name": campaign.campaign_name if campaign else "Synthetic Banking Update",
        "offer_summary": campaign.offer_summary if campaign else "A synthetic banking update is available.",
        "custom_context": case.custom_context,
    }
    subject = _render(template.subject, context)
    preheader = _render(template.preheader, context)
    body = _render(template.body, context)
    if case.custom_context:
        body = f"{body} Context note: {case.custom_context}"
    cta = _render(template.call_to_action, context)
    return EmailAutomationDraft(
        draft_id=f"DRAFT-{case.case_id}",
        case_id=case.case_id,
        customer_id=case.customer_id,
        communication_type=case.communication_type,
        event_type=case.event_type,
        campaign_id=case.campaign_id,
        subject=subject,
        preheader=preheader,
        body=body,
        call_to_action=cta,
        provider_used="template-baseline",
        model_name="template_engine",
        generation_status="baseline",
        confidence=0.72,
        compliance_status="Needs Review",
        risk_level="Medium",
        required_disclosures=template.required_disclosures,
        personalization_used=["first_name", "segment", "masked_account"],
    )
