from __future__ import annotations

import hashlib
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.data_paths import get_use_case_data_dir

USE_CASE_SLUG = "workflow-orchestration"
GENERATION_SEED = 1010
CASE_COUNT = 24
STARTUP_CASE_COUNT = 12
HELDOUT_CASE_COUNT = 12
REFERENCE_DATE = date(2026, 6, 1)

WORKFLOW_TYPES = [
    "retail_account_opening",
    "smb_lending_onboarding",
    "card_dispute_escalation",
    "cash_liquidity_exception",
]

DEPENDENCY_SLUGS = {
    "retail_account_opening": ["kyc-kyb", "document-ocr", "support-chatbot", "email-automation"],
    "smb_lending_onboarding": ["credit-risk", "kyc-kyb", "aml-monitoring", "document-ocr"],
    "card_dispute_escalation": ["fraud-detection", "support-chatbot", "document-ocr", "email-automation"],
    "cash_liquidity_exception": ["liquidity-forecast", "aml-monitoring", "market-intelligence", "email-automation"],
}


def workflow_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def workflow_raw_root() -> Path:
    return workflow_data_root() / "raw"


def metadata_path() -> Path:
    return workflow_data_root() / "metadata.json"


def ground_truth_path() -> Path:
    return workflow_data_root() / "ground_truth.json"


def workflow_definitions_path() -> Path:
    return workflow_raw_root() / "workflows" / "workflow_definitions.json"


def sla_policy_path() -> Path:
    return workflow_raw_root() / "policies" / "orchestration_sla_policy.pdf"


def dependency_contracts_path() -> Path:
    return workflow_raw_root() / "integrations" / "dependency_contracts.json"


def startup_cases_path() -> Path:
    return workflow_raw_root() / "evaluation" / "startup_cases.json"


def heldout_cases_path() -> Path:
    return workflow_raw_root() / "evaluation" / "heldout_cases.json"


def case_dir(case_id: str) -> Path:
    return workflow_raw_root() / "cases" / case_id


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
        pdf.drawString(54, y, line[:112])
        y -= 15
    pdf.save()


def _write_identity_image(path: Path, *, subject_name: str, subject_id: str, workflow_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (920, 560), color=(24, 24, 27))
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arial.ttf", 34)
        body_font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rectangle((28, 28, 892, 532), outline=(16, 185, 129), width=4)
    draw.text((60, 70), "Synthetic Identity Or Signatory Evidence", fill=(236, 253, 245), font=title_font)
    draw.text((60, 150), f"Subject: {subject_name}", fill=(244, 244, 245), font=body_font)
    draw.text((60, 200), f"Subject ID: {subject_id}", fill=(212, 212, 216), font=body_font)
    draw.text((60, 250), f"Workflow: {workflow_type.replace('_', ' ').title()}", fill=(212, 212, 216), font=body_font)
    draw.text((60, 330), "Generated sample image for local orchestration testing.", fill=(161, 161, 170), font=body_font)
    image.save(path, "JPEG", quality=92)


def _risk_level(score: float) -> str:
    if score >= 0.86:
        return "Critical"
    if score >= 0.66:
        return "High"
    if score >= 0.38:
        return "Medium"
    return "Low"


def _expected_next_actions(status: str, workflow_type: str) -> list[str]:
    if status == "Straight Through Approved":
        return ["Complete automated checklist", "Notify the synthetic relationship owner"]
    if status == "Rejected":
        return ["Record rejection reason", "Send compliant synthetic notice", "Close the workflow case"]
    if status == "Blocked":
        return ["Request missing evidence", "Pause SLA clock after intake review", "Reopen when blockers are resolved"]
    if status == "Escalated":
        return ["Assign escalation owner", "Prepare supervisor review package", "Track same-day follow-up"]
    return [
        "Assign manual review queue",
        f"Validate {workflow_type.replace('_', ' ')} evidence",
        "Update next action before SLA due time",
    ]


def _expected_status_and_owner(workflow_type: str, risk_score: float, blockers: list[str]) -> tuple[str, str]:
    base_owner = {
        "retail_account_opening": "Retail Onboarding Team",
        "smb_lending_onboarding": "SMB Credit Operations",
        "card_dispute_escalation": "Card Disputes Desk",
        "cash_liquidity_exception": "Treasury Operations",
    }[workflow_type]
    if "identity_mismatch" in blockers:
        return "Rejected", "Risk Review Committee"
    if "incomplete_documents" in blockers or "missing_dependency_evidence" in blockers:
        return "Blocked", "Intake Operations"
    if risk_score >= 0.86:
        return "Escalated", "Case Escalation Team"
    if risk_score >= 0.42 or blockers:
        return "Needs Review", base_owner
    return "Straight Through Approved", base_owner


def _case_profile(index: int) -> dict[str, Any]:
    workflow_type = WORKFLOW_TYPES[(index - 1) % len(WORKFLOW_TYPES)]
    priority = "Urgent" if index % 6 == 0 else ("Elevated" if index % 3 == 0 else "Standard")
    risk_score = round(0.12 + (index % 10) * 0.075 + (0.09 if priority == "Urgent" else 0), 3)
    blockers: list[str] = []
    if index % 7 == 0:
        blockers.append("incomplete_documents")
    if index % 11 == 0:
        blockers.append("missing_dependency_evidence")
    if index % 13 == 0:
        blockers.append("identity_mismatch")
    if index % 9 == 0:
        blockers.append("sla_breach_risk")
    if workflow_type == "retail_account_opening" and index % 5 == 0:
        blockers.append("kyc_exception")
    if workflow_type == "cash_liquidity_exception" and index % 8 == 0:
        blockers.append("vault_capacity_exception")
    expected_status, expected_owner = _expected_status_and_owner(workflow_type, risk_score, blockers)
    subject_prefix = "Business" if workflow_type == "smb_lending_onboarding" else "Customer"
    subject_id = f"{'BUS' if subject_prefix == 'Business' else 'CUST'}-WF-{index:04d}"
    requested_product = {
        "retail_account_opening": "Everyday Checking",
        "smb_lending_onboarding": "Working Capital Line",
        "card_dispute_escalation": "Card Dispute Case",
        "cash_liquidity_exception": "Cash Replenishment Exception",
    }[workflow_type]
    return {
        "case_id": f"case_{index:04d}",
        "workflow_type": workflow_type,
        "subject_id": subject_id,
        "subject_name": f"Synthetic {subject_prefix} {index:04d}",
        "priority": priority,
        "region": ["Northeast", "Midwest", "South", "West"][index % 4],
        "requested_product": requested_product,
        "created_at": (REFERENCE_DATE - timedelta(days=index % 14)).isoformat(),
        "sla_hours": 8 if priority == "Urgent" else (24 if priority == "Elevated" else 48),
        "dependency_slugs": DEPENDENCY_SLUGS[workflow_type],
        "blockers": blockers,
        "risk_score": min(risk_score, 0.97),
        "risk_signals": {
            "risk_level": _risk_level(min(risk_score, 0.97)),
            "document_gap_count": int("incomplete_documents" in blockers) + (index % 3),
            "dependency_gap_count": int("missing_dependency_evidence" in blockers),
            "customer_contact_count": 1 + (index % 5),
            "transaction_amount": round(2500 + index * 420.75, 2),
            "manual_touch_count": index % 4,
        },
        "expected_owner": expected_owner,
        "expected_final_status": expected_status,
        "expected_next_actions": _expected_next_actions(expected_status, workflow_type),
        "documents": ["case_profile.json", "customer_or_business_form.xlsx", "document_bundle.pdf", "identity_or_signatory.jpg"],
        "transaction_context": {
            "recent_transaction_count": 3 + index % 8,
            "largest_transaction_amount": round(1500 + index * 318.25, 2),
            "unusual_activity_flag": bool(index % 6 == 0 or workflow_type == "card_dispute_escalation"),
        },
        "communications_context": {
            "last_contact_channel": ["branch", "contact_center", "secure_message", "relationship_manager"][index % 4],
            "open_customer_messages": index % 3,
            "complaint_flag": bool(workflow_type == "card_dispute_escalation" and index % 2 == 0),
        },
    }


def _workflow_definitions() -> list[dict[str, Any]]:
    return [
        {
            "workflow_type": "retail_account_opening",
            "title": "Retail Account Opening",
            "description": "Coordinate document extraction, KYC review, support guidance, and customer notification.",
            "steps": [
                {"step_id": "intake", "title": "Create intake package", "owner": "Retail Onboarding Team", "depends_on": [], "required_dependencies": [], "sla_minutes": 10},
                {"step_id": "document_check", "title": "Validate document bundle", "owner": "Document Operations", "depends_on": ["intake"], "required_dependencies": ["document-ocr"], "sla_minutes": 20},
                {"step_id": "kyc_decision", "title": "Apply KYC decision", "owner": "KYC Operations", "depends_on": ["document_check"], "required_dependencies": ["kyc-kyb"], "sla_minutes": 30},
                {"step_id": "communication", "title": "Prepare customer communication", "owner": "Customer Communications", "depends_on": ["kyc_decision"], "required_dependencies": ["email-automation", "support-chatbot"], "sla_minutes": 15},
            ],
        },
        {
            "workflow_type": "smb_lending_onboarding",
            "title": "SMB Lending Onboarding",
            "description": "Coordinate credit risk, KYB, AML, and document evidence for synthetic business lending.",
            "steps": [
                {"step_id": "business_intake", "title": "Create business lending intake", "owner": "SMB Credit Operations", "depends_on": [], "required_dependencies": [], "sla_minutes": 15},
                {"step_id": "credit_review", "title": "Review credit risk output", "owner": "Credit Risk Team", "depends_on": ["business_intake"], "required_dependencies": ["credit-risk"], "sla_minutes": 40},
                {"step_id": "kyb_review", "title": "Review KYB and AML evidence", "owner": "Compliance Operations", "depends_on": ["credit_review"], "required_dependencies": ["kyc-kyb", "aml-monitoring"], "sla_minutes": 45},
                {"step_id": "final_packaging", "title": "Assemble approval package", "owner": "SMB Credit Operations", "depends_on": ["kyb_review"], "required_dependencies": ["document-ocr"], "sla_minutes": 20},
            ],
        },
        {
            "workflow_type": "card_dispute_escalation",
            "title": "Card Dispute Escalation",
            "description": "Coordinate fraud signals, dispute documents, support policy, and customer messaging.",
            "steps": [
                {"step_id": "dispute_intake", "title": "Open dispute case", "owner": "Card Disputes Desk", "depends_on": [], "required_dependencies": [], "sla_minutes": 10},
                {"step_id": "fraud_signal_review", "title": "Review fraud model signal", "owner": "Fraud Operations", "depends_on": ["dispute_intake"], "required_dependencies": ["fraud-detection"], "sla_minutes": 25},
                {"step_id": "policy_review", "title": "Apply dispute policy guidance", "owner": "Card Disputes Desk", "depends_on": ["fraud_signal_review"], "required_dependencies": ["support-chatbot", "document-ocr"], "sla_minutes": 20},
                {"step_id": "notice_draft", "title": "Draft customer dispute notice", "owner": "Customer Communications", "depends_on": ["policy_review"], "required_dependencies": ["email-automation"], "sla_minutes": 15},
            ],
        },
        {
            "workflow_type": "cash_liquidity_exception",
            "title": "Cash Liquidity Exception",
            "description": "Coordinate cash forecast, AML context, market intelligence, and operational notifications.",
            "steps": [
                {"step_id": "cash_exception_intake", "title": "Open cash exception case", "owner": "Treasury Operations", "depends_on": [], "required_dependencies": [], "sla_minutes": 10},
                {"step_id": "forecast_review", "title": "Review liquidity forecast", "owner": "Treasury Forecasting", "depends_on": ["cash_exception_intake"], "required_dependencies": ["liquidity-forecast"], "sla_minutes": 20},
                {"step_id": "risk_context", "title": "Review AML and market context", "owner": "Operational Risk", "depends_on": ["forecast_review"], "required_dependencies": ["aml-monitoring", "market-intelligence"], "sla_minutes": 25},
                {"step_id": "branch_notification", "title": "Prepare branch communication", "owner": "Customer Communications", "depends_on": ["risk_context"], "required_dependencies": ["email-automation"], "sla_minutes": 15},
            ],
        },
    ]


def _write_case_artifacts(profile: dict[str, Any]) -> None:
    root = case_dir(profile["case_id"])
    _write_json(root / "case_profile.json", profile)
    _write_xlsx(
        root / "customer_or_business_form.xlsx",
        "case_form",
        [
            {
                "case_id": profile["case_id"],
                "subject_id": profile["subject_id"],
                "subject_name": profile["subject_name"],
                "workflow_type": profile["workflow_type"],
                "requested_product": profile["requested_product"],
                "priority": profile["priority"],
                "region": profile["region"],
                "risk_score": profile["risk_score"],
            }
        ],
    )
    transaction_rows = [
        {
            "case_id": profile["case_id"],
            "transaction_id": f"{profile['case_id'].upper()}-TXN-{offset:02d}",
            "amount": round(profile["transaction_context"]["largest_transaction_amount"] / (offset + 1), 2),
            "channel": ["card", "wire", "atm", "branch"][offset % 4],
            "risk_note": "Synthetic context row for workflow orchestration.",
        }
        for offset in range(1, 7)
    ]
    _write_xlsx(root / "transaction_context.xlsx", "transactions", transaction_rows)
    _write_pdf(
        root / "document_bundle.pdf",
        f"Synthetic Workflow Document Bundle {profile['case_id']}",
        [
            f"Case ID: {profile['case_id']}",
            f"Subject: {profile['subject_name']} ({profile['subject_id']})",
            f"Workflow Type: {profile['workflow_type']}",
            f"Priority: {profile['priority']}",
            f"Requested Product: {profile['requested_product']}",
            f"Blockers: {', '.join(profile['blockers']) or 'None'}",
            "This generated bundle is synthetic and safe for local workflow testing.",
        ],
    )
    _write_identity_image(
        root / "identity_or_signatory.jpg",
        subject_name=profile["subject_name"],
        subject_id=profile["subject_id"],
        workflow_type=profile["workflow_type"],
    )
    _write_json(
        root / "communications_context.json",
        {
            "case_id": profile["case_id"],
            "subject_id": profile["subject_id"],
            "messages": [
                {
                    "message_id": f"{profile['case_id'].upper()}-MSG-01",
                    "channel": profile["communications_context"]["last_contact_channel"],
                    "summary": "Synthetic customer contact requesting workflow status.",
                },
                {
                    "message_id": f"{profile['case_id'].upper()}-MSG-02",
                    "channel": "internal_note",
                    "summary": "Synthetic operations note for next best action review.",
                },
            ],
        },
    )


def write_artifacts() -> dict[str, str]:
    random.seed(GENERATION_SEED)
    root = workflow_data_root()
    if root.exists():
        shutil.rmtree(root)
    workflow_raw_root().mkdir(parents=True, exist_ok=True)

    cases = [_case_profile(index) for index in range(1, CASE_COUNT + 1)]
    for profile in cases:
        _write_case_artifacts(profile)

    definitions = _workflow_definitions()
    _write_json(workflow_definitions_path(), definitions)
    _write_pdf(
        sla_policy_path(),
        "Synthetic Workflow Orchestration SLA Policy",
        [
            "Urgent workflow cases must receive same-day operational review within 8 hours.",
            "Elevated workflow cases must receive next-business-day review within 24 hours.",
            "Standard workflow cases must receive review within 48 hours.",
            "Deterministic rules are authoritative; LLM summaries are explanatory only.",
            "No real approvals, payments, emails, or compliance actions are executed by this MVP.",
        ],
    )
    _write_json(
        dependency_contracts_path(),
        {
            "contracts": [
                {
                    "use_case_slug": slug,
                    "required_fields": ["summary", "provider_used", "created_at"],
                    "fallback_behavior": "Record warning and use synthetic case evidence when latest output is missing.",
                }
                for slugs in DEPENDENCY_SLUGS.values()
                for slug in slugs
            ]
        },
    )
    startup_ids = [profile["case_id"] for profile in cases[:STARTUP_CASE_COUNT]]
    heldout_ids = [profile["case_id"] for profile in cases[STARTUP_CASE_COUNT:]]
    _write_json(startup_cases_path(), {"case_ids": startup_ids})
    _write_json(heldout_cases_path(), {"case_ids": heldout_ids})

    ground_truth_cases = [
        {
            "case_id": profile["case_id"],
            "workflow_type": profile["workflow_type"],
            "expected_final_status": profile["expected_final_status"],
            "expected_owner": profile["expected_owner"],
            "required_dependency_slugs": profile["dependency_slugs"],
            "expected_blockers": profile["blockers"],
            "expected_next_actions": profile["expected_next_actions"],
        }
        for profile in cases
    ]
    ground_truth = {
        "generation_seed": GENERATION_SEED,
        "case_count": len(cases),
        "startup_case_count": len(startup_ids),
        "heldout_case_count": len(heldout_ids),
        "workflow_types": WORKFLOW_TYPES,
        "cases": ground_truth_cases,
    }
    _write_json(ground_truth_path(), ground_truth)

    artifact_paths = sorted(path for path in workflow_raw_root().rglob("*") if path.is_file()) + [ground_truth_path()]
    metadata = {
        "generation_seed": GENERATION_SEED,
        "case_count": len(cases),
        "startup_case_count": len(startup_ids),
        "heldout_case_count": len(heldout_ids),
        "workflow_type_count": len(WORKFLOW_TYPES),
        "artifact_count": len(artifact_paths) + 1,
        "workflow_types": WORKFLOW_TYPES,
        "artifact_checksums": {
            str(path.resolve().relative_to(root.resolve())).replace("\\", "/"): _sha256(path)
            for path in artifact_paths
        },
    }
    _write_json(metadata_path(), metadata)

    return {
        "raw_root": str(workflow_raw_root().resolve()),
        "cases": str((workflow_raw_root() / "cases").resolve()),
        "workflow_definitions": str(workflow_definitions_path().resolve()),
        "sla_policy": str(sla_policy_path().resolve()),
        "dependency_contracts": str(dependency_contracts_path().resolve()),
        "startup_cases": str(startup_cases_path().resolve()),
        "heldout_cases": str(heldout_cases_path().resolve()),
        "ground_truth": str(ground_truth_path().resolve()),
        "metadata": str(metadata_path().resolve()),
    }
