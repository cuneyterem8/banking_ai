from __future__ import annotations

import hashlib
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.data_paths import get_use_case_data_dir

USE_CASE_SLUG = "email-automation"
GENERATION_SEED = 8808
CUSTOMER_COUNT = 120
SERVICE_EVENT_COUNT = 80
CAMPAIGN_AUDIENCE_COUNT = 40
EVALUATION_CASE_COUNT = 24
REFERENCE_DATE = date(2026, 6, 1)

SERVICE_EVENT_TYPES = [
    "card_replacement",
    "failed_payment",
    "suspicious_login_notice",
    "statement_ready",
    "loan_payment_reminder",
    "overdraft_warning",
    "kyc_refresh_reminder",
    "branch_appointment_reminder",
]
CAMPAIGN_TYPES = [
    "savings_rate_offer",
    "credit_card_upgrade",
    "small_business_cash_management",
    "mortgage_refinance_education",
    "digital_banking_adoption",
]
SEGMENTS = ["Retail Everyday", "Mass Affluent", "Small Business", "Home Lending", "Digital First"]
LIFECYCLE_STAGES = ["New", "Active", "Dormant", "Renewal", "Growth"]


def email_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def email_raw_root() -> Path:
    return email_data_root() / "raw"


def metadata_path() -> Path:
    return email_data_root() / "metadata.json"


def ground_truth_path() -> Path:
    return email_data_root() / "ground_truth.json"


def customer_profiles_path() -> Path:
    return email_raw_root() / "customers" / "customer_profiles.xlsx"


def customer_events_path() -> Path:
    return email_raw_root() / "events" / "customer_events.json"


def campaign_plan_path() -> Path:
    return email_raw_root() / "campaigns" / "campaign_plan.xlsx"


def service_templates_path() -> Path:
    return email_raw_root() / "templates" / "service_templates.txt"


def campaign_templates_path() -> Path:
    return email_raw_root() / "templates" / "campaign_templates.txt"


def email_compliance_policy_path() -> Path:
    return email_raw_root() / "policies" / "email_compliance_policy.pdf"


def tone_guidelines_path() -> Path:
    return email_raw_root() / "policies" / "tone_and_brand_guidelines.pdf"


def evaluation_cases_path() -> Path:
    return email_raw_root() / "evaluation" / "email_generation_cases.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_xlsx(path: Path, sheet_name: str, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    headers = list(rows[0]) if rows else ["status"]
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    workbook.save(path)
    workbook.close()


def _write_pdf(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 54
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(54, y, title)
    y -= 28
    pdf.setFont("Helvetica", 10)
    for line in lines:
        if y < 64:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 54
        pdf.drawString(54, y, line[:110])
        y -= 15
    pdf.save()


def _customers() -> list[dict[str, Any]]:
    customers: list[dict[str, Any]] = []
    for index in range(1, CUSTOMER_COUNT + 1):
        segment = SEGMENTS[index % len(SEGMENTS)]
        customers.append(
            {
                "customer_id": f"EMAIL-CUST-{index:04d}",
                "first_name": f"Customer{index:03d}",
                "segment": segment,
                "lifecycle_stage": LIFECYCLE_STAGES[index % len(LIFECYCLE_STAGES)],
                "preferred_channel": "email",
                "synthetic_email": f"customer{index:03d}@synthetic.example",
                "masked_account": f"****{7000 + index}",
                "locale": "en-US",
                "marketing_opt_in": index % 6 != 0,
            }
        )
    return customers


def _service_events(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index in range(1, SERVICE_EVENT_COUNT + 1):
        customer = customers[(index * 3) % len(customers)]
        event_type = SERVICE_EVENT_TYPES[index % len(SERVICE_EVENT_TYPES)]
        event_date = REFERENCE_DATE + timedelta(days=index % 20)
        events.append(
            {
                "event_id": f"EVT-{index:04d}",
                "customer_id": customer["customer_id"],
                "event_type": event_type,
                "event_date": event_date.isoformat(),
                "product_name": "Everyday Banking" if index % 3 else "Synthetic Visa Card",
                "masked_account": customer["masked_account"],
                "amount_due": round(45 + (index % 9) * 18.75, 2) if "payment" in event_type or "overdraft" in event_type else None,
                "due_date": (event_date + timedelta(days=7)).isoformat() if "payment" in event_type else None,
                "branch_name": f"Synthetic Branch {index % 8 + 1}",
                "context": {
                    "support_phone": "1-800-000-0101",
                    "secure_message_center": "Synthetic Online Banking Message Center",
                    "appointment_time": "10:30 AM" if event_type == "branch_appointment_reminder" else None,
                },
            }
        )
    return events


def _campaigns(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    campaigns: list[dict[str, Any]] = []
    for index in range(1, CAMPAIGN_AUDIENCE_COUNT + 1):
        customer = customers[(index * 5) % len(customers)]
        campaign_type = CAMPAIGN_TYPES[index % len(CAMPAIGN_TYPES)]
        campaign_id = f"CMP-{(index - 1) % len(CAMPAIGN_TYPES) + 1:03d}"
        campaigns.append(
            {
                "audience_id": f"AUD-{index:04d}",
                "campaign_id": campaign_id,
                "campaign_name": campaign_type.replace("_", " ").title(),
                "campaign_type": campaign_type,
                "customer_id": customer["customer_id"],
                "segment": customer["segment"],
                "offer_summary": {
                    "savings_rate_offer": "A featured savings account educational offer with a current disclosed rate.",
                    "credit_card_upgrade": "A card upgrade invitation subject to eligibility review.",
                    "small_business_cash_management": "A cash management consultation for eligible business customers.",
                    "mortgage_refinance_education": "A refinance education message with no approval guarantee.",
                    "digital_banking_adoption": "A reminder to try secure digital banking features.",
                }[campaign_type],
                "required_disclosure": "Marketing opt-out instructions are required.",
                "opt_out_required": True,
            }
        )
    return campaigns


def _template_block(template_key: str, communication_type: str, subject: str, preheader: str, body: str, cta: str, disclosures: list[str]) -> str:
    return "\n".join(
        [
            f"[{template_key}]",
            f"communication_type={communication_type}",
            f"subject={subject}",
            f"preheader={preheader}",
            f"body={body}",
            f"call_to_action={cta}",
            f"required_disclosures={' | '.join(disclosures)}",
            "",
        ]
    )


def _write_templates() -> None:
    service_blocks = []
    for event_type in SERVICE_EVENT_TYPES:
        service_blocks.append(
            _template_block(
                f"service:{event_type}",
                "service",
                "${first_name}, ${event_label} for ${product_name}",
                "Review this service update for account ${masked_account}.",
                (
                    "Hello ${first_name}, we are contacting you about ${event_label} for ${product_name}. "
                    "This notice references account ${masked_account}. ${service_detail} "
                    "Please use secure online banking or call ${support_phone} if you need help."
                ),
                "Review your secure message",
                ["This service message is not a marketing offer."],
            )
        )
    campaign_blocks = []
    for campaign_type in CAMPAIGN_TYPES:
        campaign_blocks.append(
            _template_block(
                f"campaign:{campaign_type}",
                "campaign",
                "${first_name}, explore ${campaign_name}",
                "A synthetic banking offer selected for your ${segment} profile.",
                (
                    "Hello ${first_name}, ${offer_summary} This message was prepared for your ${segment} profile. "
                    "You can review details in online banking. You may opt out of marketing emails at any time."
                ),
                "View details",
                ["Marketing opt-out instructions are required."],
            )
        )
    service_templates_path().parent.mkdir(parents=True, exist_ok=True)
    service_templates_path().write_text("".join(service_blocks), encoding="utf-8")
    campaign_templates_path().write_text("".join(campaign_blocks), encoding="utf-8")


def _evaluation_cases(events: list[dict[str, Any]], campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, event in enumerate(events[:14], start=1):
        cases.append(
            {
                "case_id": f"EMAIL-CASE-{index:03d}",
                "communication_type": "service",
                "customer_id": event["customer_id"],
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "campaign_id": None,
                "audience_id": None,
                "template_key": f"service:{event['event_type']}",
                "custom_context": "Use a clear service tone and avoid promotional language.",
                "expected_required_disclosures": ["This service message is not a marketing offer."],
            }
        )
    for offset, campaign in enumerate(campaigns[:10], start=15):
        cases.append(
            {
                "case_id": f"EMAIL-CASE-{offset:03d}",
                "communication_type": "campaign",
                "customer_id": campaign["customer_id"],
                "event_id": None,
                "event_type": None,
                "campaign_id": campaign["campaign_id"],
                "audience_id": campaign["audience_id"],
                "template_key": f"campaign:{campaign['campaign_type']}",
                "custom_context": "Include opt-out language and do not imply guaranteed approval.",
                "expected_required_disclosures": ["Marketing opt-out instructions are required."],
            }
        )
    return cases[:EVALUATION_CASE_COUNT]


def write_artifacts() -> dict[str, str]:
    random.seed(GENERATION_SEED)
    root = email_data_root()
    if root.exists():
        shutil.rmtree(root)
    email_raw_root().mkdir(parents=True, exist_ok=True)

    customers = _customers()
    events = _service_events(customers)
    campaigns = _campaigns(customers)
    cases = _evaluation_cases(events, campaigns)

    _write_xlsx(customer_profiles_path(), "customer_profiles", customers)
    _write_json(customer_events_path(), events)
    _write_xlsx(campaign_plan_path(), "campaign_plan", campaigns)
    _write_templates()
    _write_json(evaluation_cases_path(), cases)
    _write_pdf(
        email_compliance_policy_path(),
        "Synthetic Email Compliance Policy",
        [
            "Marketing emails must include clear opt-out instructions.",
            "Drafts must not include full account, card, tax, or government identifiers.",
            "Campaign drafts must not promise guaranteed approval, guaranteed rates, or risk-free outcomes.",
            "Every draft must include a clear call to action and required disclosures.",
            "Service emails must stay informational and avoid promotional language.",
        ],
    )
    _write_pdf(
        tone_guidelines_path(),
        "Synthetic Tone And Brand Guidelines",
        [
            "Use concise, respectful, plain English.",
            "Lead with the customer action or service update.",
            "Avoid pressure language, exaggerated urgency, or misleading benefit claims.",
            "Use synthetic support references only.",
            "Never include real customer data.",
        ],
    )

    ground_truth = {
        "generation_seed": GENERATION_SEED,
        "customer_count": len(customers),
        "service_event_count": len(events),
        "campaign_audience_count": len(campaigns),
        "evaluation_case_count": len(cases),
        "expected_case_ids": [case["case_id"] for case in cases],
        "required_rule_ids": [
            "no_full_identifier",
            "marketing_opt_out",
            "no_misleading_claim",
            "has_call_to_action",
            "required_disclosure_present",
        ],
    }
    _write_json(ground_truth_path(), ground_truth)

    artifact_paths = [
        customer_profiles_path(),
        customer_events_path(),
        campaign_plan_path(),
        service_templates_path(),
        campaign_templates_path(),
        email_compliance_policy_path(),
        tone_guidelines_path(),
        evaluation_cases_path(),
        ground_truth_path(),
    ]
    metadata = {
        "generation_seed": GENERATION_SEED,
        "customer_count": len(customers),
        "service_event_count": len(events),
        "campaign_audience_count": len(campaigns),
        "evaluation_case_count": len(cases),
        "template_count": len(SERVICE_EVENT_TYPES) + len(CAMPAIGN_TYPES),
        "artifact_checksums": {
            str(path.resolve().relative_to(root.resolve())).replace("\\", "/"): _sha256(path)
            for path in artifact_paths
        },
    }
    _write_json(metadata_path(), metadata)
    artifact_paths.append(metadata_path())

    return {
        "raw_root": str(email_raw_root().resolve()),
        "customer_profiles": str(customer_profiles_path().resolve()),
        "customer_events": str(customer_events_path().resolve()),
        "campaign_plan": str(campaign_plan_path().resolve()),
        "service_templates": str(service_templates_path().resolve()),
        "campaign_templates": str(campaign_templates_path().resolve()),
        "email_compliance_policy": str(email_compliance_policy_path().resolve()),
        "tone_guidelines": str(tone_guidelines_path().resolve()),
        "evaluation_cases": str(evaluation_cases_path().resolve()),
        "ground_truth": str(ground_truth_path().resolve()),
        "metadata": str(metadata_path().resolve()),
    }
