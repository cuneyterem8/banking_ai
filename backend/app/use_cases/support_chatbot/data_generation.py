from __future__ import annotations

import hashlib
import json
import random
import shutil
import textwrap
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.data_paths import get_use_case_data_dir

USE_CASE_SLUG = "support-chatbot"
GENERATION_SEED = 4404


def support_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def support_raw_root() -> Path:
    return support_data_root() / "raw"


def metadata_path() -> Path:
    return support_data_root() / "metadata.json"


def ground_truth_path() -> Path:
    return support_data_root() / "ground_truth.json"


def _source_text(title: str, topic: str, sections: list[tuple[str, str]]) -> str:
    lines = [f"TITLE: {title}", f"TOPIC: {topic}", ""]
    for heading, body in sections:
        lines.extend([f"SECTION: {heading}", body.strip(), ""])
    return "\n".join(lines).strip() + "\n"


def _knowledge_sources() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "SUPPORT-POLICY-RETAIL",
            "source_file": "retail_banking_policy.pdf",
            "source_type": "policy",
            "topic": "retail_banking",
            "title": "Retail Banking Support Policy",
            "relative_path": "raw/policies/retail_banking_policy.pdf",
            "media_type": "application/pdf",
            "format": "pdf",
            "text": _source_text(
                "Retail Banking Support Policy",
                "retail_banking",
                [
                    (
                        "Account opening and maintenance",
                        "Agents must confirm identity, customer eligibility, tax certification, and contact details before opening or maintaining a retail account. If a document is missing, the application is paused and the customer receives a document request notice. High-risk profile changes require a KYC refresh before account maintenance is completed.",
                    ),
                    (
                        "Fee reversal policy",
                        "A single courtesy fee reversal may be offered once in a rolling twelve month period when the account is in good standing and there is no repeated overdraft pattern. Reversal requests above 75 USD, repeated requests, or requests tied to a complaint require branch manager or contact center supervisor approval.",
                    ),
                    (
                        "Wire transfer cutoff and review",
                        "Domestic wires submitted before 3:00 PM local branch time may be processed the same business day. International wires submitted before 1:00 PM local branch time may be processed the same business day. After cutoff, agents must disclose next business day processing. Unusual beneficiary changes, large wires, or KYC refresh alerts require escalation before release.",
                    ),
                    (
                        "KYC refresh reminders",
                        "KYC refresh notices are informational until the due date shown in the case record. Agents may update address, phone, email, employer, and occupation during the refresh. If the customer refuses required information, the case must be routed to compliance operations.",
                    ),
                ],
            ),
        },
        {
            "source_id": "SUPPORT-POLICY-CARD-DISPUTE",
            "source_file": "card_dispute_policy.pdf",
            "source_type": "policy",
            "topic": "card_disputes",
            "title": "Card Dispute And Fraud Support Policy",
            "relative_path": "raw/policies/card_dispute_policy.pdf",
            "media_type": "application/pdf",
            "format": "pdf",
            "text": _source_text(
                "Card Dispute And Fraud Support Policy",
                "card_disputes",
                [
                    (
                        "Unauthorized card transaction intake",
                        "When a customer reports an unauthorized card transaction, the agent must verify identity, capture the transaction date, amount, merchant, card status, and whether the card is still in the customer's possession. The card must be blocked and replaced when compromise is suspected. The case is routed to fraud support when the customer denies participation or reports account takeover indicators.",
                    ),
                    (
                        "Dispute timeline and provisional credit",
                        "Card disputes should be opened within 60 calendar days of the statement date. For eligible unauthorized debit card claims, provisional credit is reviewed within 10 business days after the dispute is opened. Agents must explain that final resolution depends on network investigation and supporting evidence.",
                    ),
                    (
                        "Escalation rules",
                        "Escalate immediately when the reported amount is above 10,000 USD, the customer reports elder abuse, the customer is traveling without replacement card access, or the claim includes suspected employee involvement. Escalation notes must include risk indicators and the customer's preferred contact method.",
                    ),
                ],
            ),
        },
        {
            "source_id": "SUPPORT-POLICY-DIGITAL",
            "source_file": "digital_banking_policy.pdf",
            "source_type": "policy",
            "topic": "digital_banking",
            "title": "Digital Banking Support Policy",
            "relative_path": "raw/policies/digital_banking_policy.pdf",
            "media_type": "application/pdf",
            "format": "pdf",
            "text": _source_text(
                "Digital Banking Support Policy",
                "digital_banking",
                [
                    (
                        "Online banking lockout",
                        "For online banking lockout, agents must verify identity using two approved factors, review recent device changes, and reset credentials only after the customer confirms a secure email or phone number. If the device risk score is high or the customer reports unexpected one-time passcodes, the agent must escalate to digital fraud support.",
                    ),
                    (
                        "Password and device reset",
                        "A password reset may be completed after authentication. A trusted device reset requires the customer to remove old devices and confirm the new device. Agents must not read one-time passcodes aloud, request full card PINs, or bypass multi-factor authentication.",
                    ),
                    (
                        "Digital payment holds",
                        "Digital payment holds are explained as risk controls. Agents may provide the hold reason category, expected review time, and next action. They must not disclose fraud model rules, internal risk scores, or monitoring thresholds.",
                    ),
                ],
            ),
        },
        {
            "source_id": "SUPPORT-PROCEDURE-CASH",
            "source_file": "branch_cash_operations.md",
            "source_type": "procedure",
            "topic": "branch_cash",
            "title": "Branch Cash Operations Procedure",
            "relative_path": "raw/procedures/branch_cash_operations.md",
            "media_type": "text/markdown",
            "format": "markdown",
            "text": _source_text(
                "Branch Cash Operations Procedure",
                "branch_cash",
                [
                    (
                        "Large cash withdrawals",
                        "For cash withdrawals above 10,000 USD, staff must verify account ownership, confirm available funds, collect the stated purpose, notify a branch manager, and complete required currency transaction reporting steps. If cash inventory is insufficient, offer an appointment or cashier's check alternative.",
                    ),
                    (
                        "Dual control",
                        "Vault access, shipment receipt, and large cash handoff require dual control by two authorized employees. Exceptions are not permitted for customer convenience. Any cash difference is logged before the end of the business day.",
                    ),
                    (
                        "Safety and customer care",
                        "If a customer appears pressured, confused, or coached during a large cash withdrawal, staff must pause the transaction and escalate to the branch manager. The customer should be moved to a private area and asked neutral safety questions.",
                    ),
                ],
            ),
        },
        {
            "source_id": "SUPPORT-PROCEDURE-ESCALATION",
            "source_file": "contact_center_escalation.md",
            "source_type": "procedure",
            "topic": "escalation",
            "title": "Contact Center Escalation Procedure",
            "relative_path": "raw/procedures/contact_center_escalation.md",
            "media_type": "text/markdown",
            "format": "markdown",
            "text": _source_text(
                "Contact Center Escalation Procedure",
                "escalation",
                [
                    (
                        "Complaint routing",
                        "A complaint is any expression of dissatisfaction about a product, service, fee, credit decision, or employee conduct. Agents must acknowledge the complaint, capture the requested resolution, tag the product, and route the case to complaint management before the end of the shift.",
                    ),
                    (
                        "Urgent escalation",
                        "Urgent escalation is required for suspected fraud in progress, threats of self-harm, elder abuse, media inquiries, legal demands, regulator contact, or customer claims of discrimination. Agents should stay on the line when safety is at risk and notify a supervisor.",
                    ),
                    (
                        "Handoff notes",
                        "Escalation notes must include customer identity status, account or case identifier, concise timeline, customer impact, requested action, and next promised contact. Agents must not include speculation or personal opinions.",
                    ),
                ],
            ),
        },
        {
            "source_id": "SUPPORT-PROCEDURE-MAINTENANCE",
            "source_file": "account_maintenance.md",
            "source_type": "procedure",
            "topic": "account_maintenance",
            "title": "Account Maintenance Procedure",
            "relative_path": "raw/procedures/account_maintenance.md",
            "media_type": "text/markdown",
            "format": "markdown",
            "text": _source_text(
                "Account Maintenance Procedure",
                "account_maintenance",
                [
                    (
                        "Address and phone changes",
                        "Address, phone, and email changes require identity verification and a confirmation notice. If the customer also requests a wire, card replacement, or password reset within 24 hours of contact change, the agent must review for account takeover risk.",
                    ),
                    (
                        "Beneficiary and ownership changes",
                        "Beneficiary updates require customer authentication and a signed instruction. Joint owner additions require all required account opening information for the new owner. Staff must not remove an owner without approved legal documentation.",
                    ),
                    (
                        "Account closure",
                        "Before closing an account, agents must check pending transactions, holds, debit cards, recurring transfers, and fees. Remaining funds are disbursed only after ownership is verified and all restrictions are cleared.",
                    ),
                ],
            ),
        },
        {
            "source_id": "SUPPORT-FAQ",
            "source_file": "customer_support_faq.json",
            "source_type": "faq",
            "topic": "support_faq",
            "title": "Customer Support FAQ",
            "relative_path": "raw/faq/customer_support_faq.json",
            "media_type": "application/json",
            "format": "json",
            "items": [
                {
                    "question": "Can an agent reverse an overdraft fee?",
                    "answer": "Yes, one courtesy fee reversal may be offered once per rolling twelve months when the account is in good standing. Requests above 75 USD or repeated requests require supervisor approval.",
                    "tags": ["fees", "retail_banking"],
                },
                {
                    "question": "How should an agent handle an unauthorized card transaction?",
                    "answer": "Verify identity, capture transaction details, block and replace the card if compromise is suspected, open the dispute, explain provisional credit review, and route the case to fraud support when the customer denies participation.",
                    "tags": ["card_disputes", "fraud"],
                },
                {
                    "question": "What is the domestic wire cutoff?",
                    "answer": "Domestic wires submitted before 3:00 PM local branch time may be processed the same business day. After cutoff, disclose next business day processing.",
                    "tags": ["wires", "retail_banking"],
                },
                {
                    "question": "What should happen during online banking lockout?",
                    "answer": "Verify the customer with two approved factors, review recent device changes, reset credentials only after secure contact confirmation, and escalate if device risk or unexpected passcodes suggest fraud.",
                    "tags": ["digital_banking", "fraud"],
                },
                {
                    "question": "When is urgent escalation required?",
                    "answer": "Urgent escalation is required for fraud in progress, elder abuse, threats of self-harm, media inquiries, legal demands, regulator contact, or discrimination claims.",
                    "tags": ["escalation"],
                },
            ],
        },
        {
            "source_id": "SUPPORT-NOTICE-FEE-2026",
            "source_file": "product_fee_update.txt",
            "source_type": "notice",
            "topic": "fee_update",
            "title": "Product Fee Update Notice",
            "relative_path": "raw/notices/product_fee_update.txt",
            "media_type": "text/plain",
            "format": "text",
            "text": _source_text(
                "Product Fee Update Notice",
                "fee_update",
                [
                    (
                        "Monthly maintenance fee update",
                        "Starting 2026-04-01, the synthetic Everyday Checking monthly maintenance fee is 8 USD unless the customer has qualifying direct deposit, minimum daily balance, or student waiver status. Agents must disclose waiver options before discussing closure.",
                    ),
                    (
                        "Debit card rush replacement",
                        "Rush debit card replacement is 20 USD. The fee may be waived when card compromise is confirmed in an open fraud case or when the replacement is caused by bank error.",
                    ),
                ],
            ),
        },
    ]


EVALUATION_CASES: list[dict[str, Any]] = [
    {
        "question_id": "SUP-Q-001",
        "question": "What should an agent do when a customer reports an unauthorized card transaction?",
        "expected_source_ids": ["SUPPORT-POLICY-CARD-DISPUTE", "SUPPORT-FAQ"],
        "must_cite": ["verify identity", "block and replace", "fraud support"],
        "expected_tags": ["card_disputes", "fraud"],
        "escalation_expected": False,
    },
    {
        "question_id": "SUP-Q-002",
        "question": "Can a contact center agent reverse an overdraft fee for a customer?",
        "expected_source_ids": ["SUPPORT-POLICY-RETAIL", "SUPPORT-FAQ"],
        "must_cite": ["once in a rolling twelve month period", "75 USD"],
        "expected_tags": ["fees", "retail_banking"],
        "escalation_expected": False,
    },
    {
        "question_id": "SUP-Q-003",
        "question": "What is the cutoff time for domestic wires?",
        "expected_source_ids": ["SUPPORT-POLICY-RETAIL", "SUPPORT-FAQ"],
        "must_cite": ["3:00 PM local branch time", "next business day"],
        "expected_tags": ["wires", "retail_banking"],
        "escalation_expected": False,
    },
    {
        "question_id": "SUP-Q-004",
        "question": "How should staff handle a customer who is locked out of online banking and mentions unexpected passcodes?",
        "expected_source_ids": ["SUPPORT-POLICY-DIGITAL", "SUPPORT-FAQ"],
        "must_cite": ["two approved factors", "unexpected one-time passcodes", "digital fraud support"],
        "expected_tags": ["digital_banking", "fraud"],
        "escalation_expected": True,
    },
    {
        "question_id": "SUP-Q-005",
        "question": "What are the branch steps for a cash withdrawal above 10000 USD?",
        "expected_source_ids": ["SUPPORT-PROCEDURE-CASH"],
        "must_cite": ["verify account ownership", "branch manager", "currency transaction reporting"],
        "expected_tags": ["branch_cash"],
        "escalation_expected": True,
    },
    {
        "question_id": "SUP-Q-006",
        "question": "How should a complaint about a fee or employee conduct be routed?",
        "expected_source_ids": ["SUPPORT-PROCEDURE-ESCALATION"],
        "must_cite": ["acknowledge the complaint", "requested resolution", "complaint management"],
        "expected_tags": ["escalation"],
        "escalation_expected": True,
    },
    {
        "question_id": "SUP-Q-007",
        "question": "What extra review is needed when a customer changes contact details and then requests a wire?",
        "expected_source_ids": ["SUPPORT-PROCEDURE-MAINTENANCE", "SUPPORT-POLICY-RETAIL"],
        "must_cite": ["within 24 hours", "account takeover risk"],
        "expected_tags": ["account_maintenance", "fraud"],
        "escalation_expected": True,
    },
    {
        "question_id": "SUP-Q-008",
        "question": "When can the rush debit card replacement fee be waived?",
        "expected_source_ids": ["SUPPORT-NOTICE-FEE-2026"],
        "must_cite": ["card compromise", "bank error"],
        "expected_tags": ["fee_update", "card_disputes"],
        "escalation_expected": False,
    },
]


def _clean_raw() -> None:
    root = support_raw_root()
    root.mkdir(parents=True, exist_ok=True)
    for path in root.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()


def _write_pdf(path: Path, title: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=letter, invariant=1)
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(54, 770, title)
    pdf.setFont("Helvetica", 9)
    y = 742
    for paragraph in text.splitlines():
        wrapped = textwrap.wrap(paragraph, width=96) if paragraph.strip() else [""]
        for line in wrapped:
            if y < 54:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y = 742
            pdf.drawString(54, y, line)
            y -= 14
    pdf.save()


def _write_markdown(path: Path, title: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("TITLE: "):
            lines.append(f"# {line.removeprefix('TITLE: ')}")
        elif line.startswith("SECTION: "):
            lines.append(f"## {line.removeprefix('SECTION: ')}")
        elif line.startswith("TOPIC: "):
            lines.append(f"Topic: {line.removeprefix('TOPIC: ')}")
        else:
            lines.append(line)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _chunk_count_for_source(source: dict[str, Any]) -> int:
    if source["format"] == "json":
        return len(source["items"])
    target_size = 900
    overlap = 120
    count = 0
    current: list[str] = []
    for line in source["text"].splitlines():
        if line.startswith("SECTION: "):
            if current:
                body = "\n".join(current).strip()
                count += 1 if len(body) <= target_size else max(1, ((len(body) - overlap - 1) // (target_size - overlap)) + 1)
            current = [line]
        elif current:
            current.append(line)
    if current:
        body = "\n".join(current).strip()
        count += 1 if len(body) <= target_size else max(1, ((len(body) - overlap - 1) // (target_size - overlap)) + 1)
    return count


def _write_source(source: dict[str, Any]) -> None:
    path = support_data_root() / source["relative_path"]
    if source["format"] == "pdf":
        _write_pdf(path, source["title"], source["text"])
    elif source["format"] == "markdown":
        _write_markdown(path, source["title"], source["text"])
    elif source["format"] == "json":
        _write_json(path, {"source_id": source["source_id"], "title": source["title"], "items": source["items"]})
    else:
        _write_text(path, source["text"])


def _manifest_record(source: dict[str, Any]) -> dict[str, Any]:
    path = support_data_root() / source["relative_path"]
    return {
        "source_id": source["source_id"],
        "source_file": source["source_file"],
        "source_type": source["source_type"],
        "topic": source["topic"],
        "title": source["title"],
        "relative_path": source["relative_path"],
        "media_type": source["media_type"],
        "checksum": _checksum(path),
    }


def build_ground_truth(seed: int = GENERATION_SEED) -> dict[str, Any]:
    random.Random(seed)
    sources = _knowledge_sources()
    return {
        "generation_seed": seed,
        "knowledge_document_count": len(sources),
        "evaluation_question_count": len(EVALUATION_CASES),
        "chunk_count": sum(_chunk_count_for_source(source) for source in sources),
        "evaluation_cases": EVALUATION_CASES,
    }


def write_artifacts() -> dict[str, str]:
    support_data_root().mkdir(parents=True, exist_ok=True)
    _clean_raw()
    sources = _knowledge_sources()
    for source in sources:
        _write_source(source)
    _write_json(
        support_raw_root() / "evaluation" / "support_questions.json",
        [
            {"question_id": item["question_id"], "question": item["question"]}
            for item in EVALUATION_CASES
        ],
    )
    source_records = [_manifest_record(source) for source in sources]
    ground_truth = build_ground_truth()
    metadata = {
        "dataset": "synthetic_support_chatbot_knowledge_base",
        "generation_seed": GENERATION_SEED,
        "knowledge_document_count": len(source_records),
        "evaluation_question_count": len(EVALUATION_CASES),
        "chunk_count": ground_truth["chunk_count"],
        "topics": sorted({source["topic"] for source in source_records}),
        "description": "Synthetic internal banking support knowledge base for local-first RAG and GPT-4o fallback.",
        "documents": source_records,
        "evaluation_file": "raw/evaluation/support_questions.json",
        "evaluation_checksum": _checksum(support_raw_root() / "evaluation" / "support_questions.json"),
    }
    metadata_path().write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    ground_truth_path().write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    return {
        "raw_root": str(support_raw_root().resolve()),
        "metadata": str(metadata_path().resolve()),
        "ground_truth": str(ground_truth_path().resolve()),
    }
