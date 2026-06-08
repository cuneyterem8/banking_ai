import hashlib
import json
import random
import shutil
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.data_paths import get_use_case_data_dir

USE_CASE_SLUG = "document-ocr"
GENERATION_SEED = 9307
CUSTOMER_COUNT = 12

DOCUMENT_TYPES = (
    "bank_statement",
    "account_confirmation",
    "income_proof",
    "scanned_statement",
    "transfer_notice",
)

CUSTOMER_NAMES = [
    "Avery Morgan",
    "Jordan Ellis",
    "Taylor Brooks",
    "Riley Chen",
    "Morgan Patel",
    "Casey Rivera",
    "Quinn Parker",
    "Jamie Bennett",
    "Drew Coleman",
    "Skyler Hughes",
    "Harper Collins",
    "Rowan Mitchell",
]

EMPLOYERS = [
    "Northwind Analytics LLC",
    "Blue Harbor Retail Group",
    "Summit Health Services",
    "Pioneer Solar Systems",
    "Cedar Point Logistics",
    "Atlas Digital Media",
]

BRANCHES = [
    "Downtown Branch",
    "North Avenue Branch",
    "Riverside Branch",
    "Market Street Branch",
    "Central Operations Branch",
]


def document_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def document_raw_root() -> Path:
    return document_data_root() / "raw"


def metadata_path() -> Path:
    return document_data_root() / "metadata.json"


def ground_truth_path() -> Path:
    return document_data_root() / "ground_truth.json"


def _customer_dir(index: int) -> Path:
    return document_raw_root() / f"customer_{index:04d}"


def _money(value: float) -> str:
    return f"{value:.2f}"


def _customer_profile(index: int, rng: random.Random) -> dict[str, Any]:
    name = CUSTOMER_NAMES[index - 1]
    account_suffix = f"{rng.randint(1000, 9999)}"
    customer_id = f"CUST-OCR-{index:04d}"
    month_start = date(2026, 1, 1) + timedelta(days=(index - 1) * 31)
    statement_start = month_start.replace(day=1)
    statement_end = statement_start + timedelta(days=29)
    opening_balance = round(3200 + rng.random() * 5200 + index * 135, 2)
    transactions = _transactions(index, statement_start, opening_balance, rng)
    closing_balance = float(transactions[-1]["balance"])
    income = round(4200 + rng.random() * 3800 + index * 85, 2)
    return {
        "customer_id": customer_id,
        "customer_name": name,
        "masked_account_number": f"****{account_suffix}",
        "iban": f"US-SYN-{index:04d}-{account_suffix}",
        "statement_period": f"{statement_start.isoformat()} to {statement_end.isoformat()}",
        "statement_start": statement_start.isoformat(),
        "statement_end": statement_end.isoformat(),
        "opening_balance": _money(opening_balance),
        "closing_balance": _money(closing_balance),
        "currency": "USD",
        "branch": BRANCHES[index % len(BRANCHES)],
        "issue_date": (statement_end + timedelta(days=3)).isoformat(),
        "account_open_date": date(2021 + index % 4, 2 + index % 8, 10 + index % 12).isoformat(),
        "account_status": "Active",
        "employer": EMPLOYERS[index % len(EMPLOYERS)],
        "employment_status": "Full-time",
        "monthly_gross_income": _money(income),
        "monthly_net_income": _money(income * 0.74),
        "payroll_date": (statement_end - timedelta(days=2)).isoformat(),
        "transactions": transactions,
    }


def _transactions(index: int, start: date, opening_balance: float, rng: random.Random) -> list[dict[str, str]]:
    descriptions = [
        "Payroll Deposit",
        "POS Grocery Market",
        "Online Utility Payment",
        "ATM Withdrawal",
        "Card Restaurant",
        "Incoming Transfer",
        "Insurance Payment",
        "Mobile Transfer",
    ]
    balance = opening_balance
    rows: list[dict[str, str]] = []
    for txn_index in range(1, 9):
        txn_date = start + timedelta(days=txn_index * 3)
        description = descriptions[(index + txn_index) % len(descriptions)]
        txn_type = "Credit" if "Payroll" in description or "Incoming" in description else "Debit"
        amount = round(rng.uniform(45, 620), 2)
        if txn_type == "Credit":
            balance += amount
        else:
            balance -= amount
        rows.append(
            {
                "date": txn_date.isoformat(),
                "description": description,
                "type": txn_type,
                "amount": _money(amount),
                "balance": _money(balance),
            }
        )
    return rows


def _draw_lines(pdf: canvas.Canvas, lines: list[str], *, start_y: int = 744) -> None:
    y = start_y
    for line in lines:
        pdf.drawString(54, y, line)
        y -= 16


def _write_text_pdf(path: Path, title: str, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter, invariant=1)
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(54, 770, title)
    pdf.setFont("Helvetica", 9)
    _draw_lines(pdf, lines)
    pdf.save()


def _statement_lines(profile: dict[str, Any], document_id: str) -> list[str]:
    lines = [
        f"Document ID: {document_id}",
        "Document Type: Bank Statement",
        f"Customer ID: {profile['customer_id']}",
        f"Customer Name: {profile['customer_name']}",
        f"Masked Account Number: {profile['masked_account_number']}",
        f"Statement Period: {profile['statement_period']}",
        f"Opening Balance: {profile['opening_balance']}",
        f"Closing Balance: {profile['closing_balance']}",
        f"Currency: {profile['currency']}",
        "",
        "Transaction Date | Description | Type | Amount | Balance",
    ]
    for row in profile["transactions"]:
        lines.append(
            f"{row['date']} | {row['description']} | {row['type']} | {row['amount']} | {row['balance']}"
        )
    return lines


def _account_lines(profile: dict[str, Any], document_id: str) -> list[str]:
    return [
        f"Document ID: {document_id}",
        "Document Type: Account Confirmation",
        f"Customer ID: {profile['customer_id']}",
        f"Customer Name: {profile['customer_name']}",
        f"Masked Account Number: {profile['masked_account_number']}",
        f"IBAN: {profile['iban']}",
        f"Branch: {profile['branch']}",
        f"Issue Date: {profile['issue_date']}",
        f"Account Open Date: {profile['account_open_date']}",
        f"Account Status: {profile['account_status']}",
        f"Currency: {profile['currency']}",
    ]


def _income_lines(profile: dict[str, Any], document_id: str) -> list[str]:
    return [
        f"Document ID: {document_id}",
        "Document Type: Income Proof",
        f"Customer ID: {profile['customer_id']}",
        f"Customer Name: {profile['customer_name']}",
        f"Employer: {profile['employer']}",
        f"Employment Status: {profile['employment_status']}",
        f"Monthly Gross Income: {profile['monthly_gross_income']}",
        f"Monthly Net Income: {profile['monthly_net_income']}",
        f"Payroll Date: {profile['payroll_date']}",
        f"Currency: {profile['currency']}",
    ]


def _notice_lines(profile: dict[str, Any], document_id: str) -> list[str]:
    amount = profile["transactions"][-1]["amount"]
    return [
        f"Document ID: {document_id}",
        "Document Type: Transfer Notice",
        f"Customer ID: {profile['customer_id']}",
        f"Customer Name: {profile['customer_name']}",
        f"Masked Account Number: {profile['masked_account_number']}",
        f"Transfer Date: {profile['transactions'][-1]['date']}",
        f"Transfer Amount: {amount}",
        f"Currency: {profile['currency']}",
        "Transfer Status: Completed",
    ]


def _write_image(path: Path, title: str, lines: list[str]) -> Image.Image:
    image = Image.new("RGB", (1450, 1900), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((90, 90), title, fill="black", font=font)
    y = 150
    for line in lines:
        draw.text((90, y), line, fill="black", font=font)
        y += 38
    # Light scan-like noise and border.
    for x in range(30, 1420, 80):
        draw.line((x, 30, x, 1870), fill=(245, 245, 245), width=1)
    draw.rectangle((45, 45, 1405, 1855), outline=(90, 90, 90), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=92)
    return image


def _write_scanned_pdf(path: Path, title: str, lines: list[str]) -> None:
    buffer = BytesIO()
    image = Image.new("RGB", (1450, 1900), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((90, 90), title, fill="black", font=font)
    y = 150
    for line in lines:
        draw.text((90, y), line, fill="black", font=font)
        y += 38
    draw.rectangle((45, 45, 1405, 1855), outline=(90, 90, 90), width=3)
    image.save(buffer, format="PNG")
    buffer.seek(0)
    pdf = canvas.Canvas(str(path), pagesize=letter, invariant=1)
    pdf.drawImage(ImageReader(buffer), 36, 36, width=540, height=720)
    pdf.save()


def _document_id(prefix: str, index: int) -> str:
    return f"DOC-{prefix}-{index:04d}"


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_to_data_root(path: Path) -> str:
    return str(path.relative_to(document_data_root())).replace("\\", "/")


def _expected_document(
    *,
    document_id: str,
    profile: dict[str, Any],
    document_type: str,
    file_name: str,
    relative_path: str,
    media_type: str,
    is_scanned: bool,
    fields: dict[str, str],
    tables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "customer_id": profile["customer_id"],
        "customer_name": profile["customer_name"],
        "document_type": document_type,
        "file_name": file_name,
        "relative_path": relative_path,
        "media_type": media_type,
        "is_scanned": is_scanned,
        "expected_fields": fields,
        "expected_tables": tables or [],
    }


def _build_customer_package(index: int, rng: random.Random) -> list[dict[str, Any]]:
    profile = _customer_profile(index, rng)
    folder = _customer_dir(index)
    folder.mkdir(parents=True, exist_ok=True)

    bs_id = _document_id("BS", index)
    ac_id = _document_id("AC", index)
    ip_id = _document_id("IP", index)
    ss_id = _document_id("SS", index)
    tn_id = _document_id("TN", index)

    paths = {
        "bank_statement": folder / "bank_statement.pdf",
        "account_confirmation": folder / "account_confirmation.pdf",
        "income_proof": folder / "income_proof.pdf",
        "scanned_statement": folder / "scanned_statement.pdf",
        "transfer_notice": folder / "transfer_notice.jpg",
    }

    _write_text_pdf(paths["bank_statement"], "Synthetic Bank Statement", _statement_lines(profile, bs_id))
    _write_text_pdf(paths["account_confirmation"], "Synthetic Account Confirmation", _account_lines(profile, ac_id))
    _write_text_pdf(paths["income_proof"], "Synthetic Income Proof", _income_lines(profile, ip_id))
    _write_scanned_pdf(paths["scanned_statement"], "Synthetic Scanned Statement", _statement_lines(profile, ss_id))
    _write_image(paths["transfer_notice"], "Synthetic Transfer Notice", _notice_lines(profile, tn_id))

    statement_fields = {
        "document_id": bs_id,
        "document_type": "Bank Statement",
        "customer_id": profile["customer_id"],
        "customer_name": profile["customer_name"],
        "masked_account_number": profile["masked_account_number"],
        "statement_period": profile["statement_period"],
        "opening_balance": profile["opening_balance"],
        "closing_balance": profile["closing_balance"],
        "currency": profile["currency"],
    }
    scanned_fields = {**statement_fields, "document_id": ss_id}
    notice_fields = {
        "document_id": tn_id,
        "document_type": "Transfer Notice",
        "customer_id": profile["customer_id"],
        "customer_name": profile["customer_name"],
        "masked_account_number": profile["masked_account_number"],
        "transfer_date": profile["transactions"][-1]["date"],
        "transfer_amount": profile["transactions"][-1]["amount"],
        "currency": profile["currency"],
        "transfer_status": "Completed",
    }
    transaction_table = [{"name": "transactions", "rows": profile["transactions"]}]

    docs = [
        _expected_document(
            document_id=bs_id,
            profile=profile,
            document_type="bank_statement",
            file_name="bank_statement.pdf",
            relative_path=_relative_to_data_root(paths["bank_statement"]),
            media_type="application/pdf",
            is_scanned=False,
            fields=statement_fields,
            tables=transaction_table,
        ),
        _expected_document(
            document_id=ac_id,
            profile=profile,
            document_type="account_confirmation",
            file_name="account_confirmation.pdf",
            relative_path=_relative_to_data_root(paths["account_confirmation"]),
            media_type="application/pdf",
            is_scanned=False,
            fields={
                "document_id": ac_id,
                "document_type": "Account Confirmation",
                "customer_id": profile["customer_id"],
                "customer_name": profile["customer_name"],
                "masked_account_number": profile["masked_account_number"],
                "iban": profile["iban"],
                "branch": profile["branch"],
                "issue_date": profile["issue_date"],
                "account_open_date": profile["account_open_date"],
                "account_status": profile["account_status"],
                "currency": profile["currency"],
            },
        ),
        _expected_document(
            document_id=ip_id,
            profile=profile,
            document_type="income_proof",
            file_name="income_proof.pdf",
            relative_path=_relative_to_data_root(paths["income_proof"]),
            media_type="application/pdf",
            is_scanned=False,
            fields={
                "document_id": ip_id,
                "document_type": "Income Proof",
                "customer_id": profile["customer_id"],
                "customer_name": profile["customer_name"],
                "employer": profile["employer"],
                "employment_status": profile["employment_status"],
                "monthly_gross_income": profile["monthly_gross_income"],
                "monthly_net_income": profile["monthly_net_income"],
                "payroll_date": profile["payroll_date"],
                "currency": profile["currency"],
            },
        ),
        _expected_document(
            document_id=ss_id,
            profile=profile,
            document_type="scanned_statement",
            file_name="scanned_statement.pdf",
            relative_path=_relative_to_data_root(paths["scanned_statement"]),
            media_type="application/pdf",
            is_scanned=True,
            fields=scanned_fields,
            tables=transaction_table,
        ),
        _expected_document(
            document_id=tn_id,
            profile=profile,
            document_type="transfer_notice",
            file_name="transfer_notice.jpg",
            relative_path=_relative_to_data_root(paths["transfer_notice"]),
            media_type="image/jpeg",
            is_scanned=True,
            fields=notice_fields,
        ),
    ]
    for doc in docs:
        doc["sha256"] = _checksum(document_data_root() / doc["relative_path"])
    return docs


def build_ground_truth(seed: int = GENERATION_SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    documents: list[dict[str, Any]] = []
    for index in range(1, CUSTOMER_COUNT + 1):
        documents.extend(_build_customer_package(index, rng))
    return {
        "generation_seed": seed,
        "customer_count": CUSTOMER_COUNT,
        "document_count": len(documents),
        "documents": documents,
    }


def _clean_raw() -> None:
    root = document_raw_root()
    root.mkdir(parents=True, exist_ok=True)
    for path in root.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()


def _manifest_from_ground_truth(ground_truth: dict[str, Any]) -> dict[str, Any]:
    documents = ground_truth["documents"]
    return {
        "dataset": "synthetic_document_ocr_banking_package",
        "generation_seed": ground_truth["generation_seed"],
        "customer_count": ground_truth["customer_count"],
        "document_count": ground_truth["document_count"],
        "document_types": list(DOCUMENT_TYPES),
        "expected_field_count": sum(len(item["expected_fields"]) for item in documents),
        "expected_table_row_count": sum(
            len(table["rows"]) for item in documents for table in item["expected_tables"]
        ),
        "description": "Synthetic banking document packages for local-first OCR extraction and GPT-4o fallback.",
        "documents": [
            {
                "document_id": item["document_id"],
                "customer_id": item["customer_id"],
                "customer_name": item["customer_name"],
                "document_type": item["document_type"],
                "file_name": item["file_name"],
                "relative_path": item["relative_path"],
                "media_type": item["media_type"],
                "is_scanned": item["is_scanned"],
                "expected_field_count": len(item["expected_fields"]),
                "expected_table_row_count": sum(len(table["rows"]) for table in item["expected_tables"]),
                "sha256": item["sha256"],
            }
            for item in documents
        ],
    }


def write_artifacts() -> dict[str, str]:
    root = document_data_root()
    root.mkdir(parents=True, exist_ok=True)
    _clean_raw()
    ground_truth = build_ground_truth()
    manifest = _manifest_from_ground_truth(ground_truth)
    metadata_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ground_truth_path().write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    return {
        "raw_root": str(document_raw_root().resolve()),
        "metadata": str(metadata_path().resolve()),
        "ground_truth": str(ground_truth_path().resolve()),
    }
