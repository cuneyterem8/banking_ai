from __future__ import annotations

import hashlib
import json
import random
import shutil
import textwrap
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.data_paths import get_use_case_data_dir

USE_CASE_SLUG = "kyc-kyb"
GENERATION_SEED = 7407
INDIVIDUAL_COUNT = 24
BUSINESS_COUNT = 24
REFERENCE_DATE = date(2026, 6, 1)
HIGH_RISK_JURISDICTIONS = ["Orchid Islands", "Northland Free Zone", "Silver Coast"]
LOW_RISK_JURISDICTIONS = ["United States", "Canada", "United Kingdom", "Germany", "France", "Netherlands"]
INDUSTRIES = ["Retail Banking", "Import Export", "Software Services", "Real Estate", "Hospitality", "Payment Services"]


def kyc_kyb_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def kyc_kyb_raw_root() -> Path:
    return kyc_kyb_data_root() / "raw"


def metadata_path() -> Path:
    return kyc_kyb_data_root() / "metadata.json"


def ground_truth_path() -> Path:
    return kyc_kyb_data_root() / "ground_truth.json"


def reference_root() -> Path:
    return kyc_kyb_raw_root() / "reference"


def sanctions_watchlist_path() -> Path:
    return reference_root() / "sanctions_watchlist.json"


def high_risk_jurisdictions_path() -> Path:
    return reference_root() / "high_risk_jurisdictions.json"


def document_policy_pdf_path() -> Path:
    return reference_root() / "document_policy.pdf"


def _reset_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for item in path.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_for(index: int) -> str:
    if index <= 16:
        return "train"
    if index <= 20:
        return "val"
    return "test"


def _write_pdf(path: Path, title: str, fields: dict[str, Any], paragraphs: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - 54
    doc.setFont("Helvetica-Bold", 14)
    doc.drawString(54, y, title)
    y -= 28
    doc.setFont("Helvetica", 9)
    for key, value in fields.items():
        for line in textwrap.wrap(f"{key}: {value}", width=96):
            doc.drawString(54, y, line)
            y -= 14
        y -= 2
    for paragraph in paragraphs or []:
        y -= 8
        for line in textwrap.wrap(paragraph, width=96):
            doc.drawString(54, y, line)
            y -= 14
            if y < 72:
                doc.showPage()
                doc.setFont("Helvetica", 9)
                y = height - 54
    doc.save()


def _write_xlsx(path: Path, sheet_name: str, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name[:31]
    headers = list(rows[0].keys()) if rows else ["status"]
    sheet.append(headers)
    if rows:
        for row in rows:
            sheet.append([row.get(header) for header in headers])
    else:
        sheet.append(["No records supplied"])
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(max(len(str(cell.value or "")) for cell in column) + 2, 34)
    workbook.save(path)


def _write_image(path: Path, title: str, fields: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (980, 620), color=(245, 248, 252))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 956, 596), outline=(55, 75, 95), width=3)
    draw.text((48, 48), title, fill=(18, 38, 63))
    y = 94
    for key, value in fields.items():
        draw.text((48, y), f"{key}: {value}", fill=(20, 20, 20))
        y += 32
    image.save(path, quality=92)


def _status_from_flags(flags: list[str]) -> str:
    if "sanctions_watchlist_match" in flags or "expired_identity_document" in flags:
        return "Rejected"
    if flags:
        return "Needs Review"
    return "Approved"


def _risk_from_flags(flags: list[str], base: float) -> float:
    weights = {
        "expired_identity_document": 0.34,
        "address_mismatch": 0.24,
        "missing_tax_certification": 0.24,
        "high_risk_jurisdiction": 0.28,
        "sanctions_watchlist_match": 0.46,
        "missing_beneficial_owner": 0.32,
        "ownership_total_incomplete": 0.22,
        "signatory_id_expired": 0.25,
        "risk_attestation_missing": 0.2,
    }
    return round(min(0.98, base + sum(weights.get(flag, 0.12) for flag in flags)), 4)


def _document(
    *,
    package_id: str,
    document_id: str,
    subject_type: str,
    document_type: str,
    file_path: Path,
    expected_fields: dict[str, Any],
    is_image: bool = False,
    local_fields_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "package_id": package_id,
        "subject_type": subject_type,
        "document_type": document_type,
        "file_name": file_path.name,
        "relative_path": str(file_path.resolve().relative_to(kyc_kyb_data_root().resolve())).replace("\\", "/"),
        "is_image": is_image,
        "expected_fields": expected_fields,
        "local_fields_hint": local_fields_hint or {},
    }


def _individual_package(index: int) -> dict[str, Any]:
    package_id = f"KYC-CUST-{index:04d}"
    folder = kyc_kyb_raw_root() / "individuals" / f"customer_{index:04d}"
    subject_name = f"Synthetic Customer {index:02d}"
    address = f"{100 + index} Cedar Street, Sample City, ST {90000 + index}"
    declared_address = address if index % 6 else f"{200 + index} Pine Avenue, Sample City, ST {91000 + index}"
    jurisdiction = HIGH_RISK_JURISDICTIONS[index % len(HIGH_RISK_JURISDICTIONS)] if index % 8 == 0 else LOW_RISK_JURISDICTIONS[index % len(LOW_RISK_JURISDICTIONS)]
    expiry_year = 2025 if index % 7 == 0 else 2031
    flags: list[str] = []
    if expiry_year < REFERENCE_DATE.year:
        flags.append("expired_identity_document")
    if declared_address != address:
        flags.append("address_mismatch")
    if jurisdiction in HIGH_RISK_JURISDICTIONS:
        flags.append("high_risk_jurisdiction")
    if index % 9 == 0:
        flags.append("missing_tax_certification")
    if index % 11 == 0:
        flags.append("sanctions_watchlist_match")

    document_number = f"ID-{500000 + index}"
    tax_status = "Missing Certification" if "missing_tax_certification" in flags else "Complete"
    front_fields = {
        "Document Type": "Synthetic Government ID Front",
        "Full Name": subject_name,
        "Document Number": document_number,
        "Date Of Birth": f"19{78 + index % 16}-0{1 + index % 8}-15",
        "Issue Date": "2022-04-15",
        "Expiry Date": f"{expiry_year}-04-15",
        "Nationality": jurisdiction,
    }
    back_fields = {
        "Document Type": "Synthetic Government ID Back",
        "Full Name": subject_name,
        "Document Number": document_number,
        "Address": address,
    }
    address_fields = {
        "Customer Name": subject_name,
        "Address": address,
        "Issue Date": "2026-05-03",
        "Document Purpose": "Proof Of Address",
    }
    employment_fields = {
        "Customer Name": subject_name,
        "Employer": f"Synthetic Employer {index % 7 + 1}",
        "Employment Status": "Employed",
        "Occupation": "Operations Specialist",
        "Issue Date": "2026-05-12",
    }
    tax_fields = {
        "Subject Name": subject_name,
        "Tax ID": f"TAX-{700000 + index}",
        "Certification Status": tax_status,
        "Signature Date": "2026-05-15",
    }
    onboarding_fields = {
        "Subject Name": subject_name,
        "Declared Address": declared_address,
        "Jurisdiction": jurisdiction,
        "Purpose Of Account": "Personal banking",
        "Expected Monthly Volume": 4500 + index * 120,
    }

    front_path = folder / "id_document_front.jpg"
    back_path = folder / "id_document_back.jpg"
    address_path = folder / "proof_of_address.pdf"
    employment_path = folder / "employment_letter.pdf"
    tax_path = folder / "tax_certification.xlsx"
    onboarding_path = folder / "onboarding_form.xlsx"
    _write_image(front_path, "Synthetic ID Front", front_fields)
    _write_image(back_path, "Synthetic ID Back", back_fields)
    _write_pdf(address_path, "Synthetic Proof Of Address", address_fields)
    _write_pdf(employment_path, "Synthetic Employment Letter", employment_fields)
    _write_xlsx(tax_path, "tax_certification", [tax_fields])
    _write_xlsx(onboarding_path, "onboarding_form", [onboarding_fields])

    documents = [
        _document(package_id=package_id, document_id=f"{package_id}-ID-FRONT", subject_type="individual", document_type="id_document_front", file_path=front_path, expected_fields=front_fields, is_image=True, local_fields_hint=front_fields),
        _document(package_id=package_id, document_id=f"{package_id}-ID-BACK", subject_type="individual", document_type="id_document_back", file_path=back_path, expected_fields=back_fields, is_image=True, local_fields_hint=back_fields),
        _document(package_id=package_id, document_id=f"{package_id}-ADDRESS", subject_type="individual", document_type="proof_of_address", file_path=address_path, expected_fields=address_fields),
        _document(package_id=package_id, document_id=f"{package_id}-EMPLOYMENT", subject_type="individual", document_type="employment_letter", file_path=employment_path, expected_fields=employment_fields),
        _document(package_id=package_id, document_id=f"{package_id}-TAX", subject_type="individual", document_type="tax_certification", file_path=tax_path, expected_fields=tax_fields),
        _document(package_id=package_id, document_id=f"{package_id}-FORM", subject_type="individual", document_type="onboarding_form", file_path=onboarding_path, expected_fields=onboarding_fields),
    ]
    return {
        "package_id": package_id,
        "subject_type": "individual",
        "subject_name": subject_name,
        "split": _split_for(index),
        "jurisdiction": jurisdiction,
        "address": address,
        "expected_status": _status_from_flags(flags),
        "label_manual_review_required": 1 if flags else 0,
        "expected_risk_score": _risk_from_flags(flags, 0.16 + (index % 5) * 0.025),
        "expected_rule_flags": flags,
        "documents": documents,
    }


def _business_package(index: int) -> dict[str, Any]:
    package_id = f"KYB-COMP-{index:04d}"
    folder = kyc_kyb_raw_root() / "businesses" / f"company_{index:04d}"
    company_name = f"Synthetic Company {index:02d} LLC"
    signatory_name = f"Synthetic Signatory {index:02d}"
    address = f"{400 + index} Market Road, Commerce City, ST {80000 + index}"
    proof_address = address if index % 6 else f"{500 + index} Harbor Road, Commerce City, ST {81000 + index}"
    jurisdiction = HIGH_RISK_JURISDICTIONS[index % len(HIGH_RISK_JURISDICTIONS)] if index % 7 == 0 else LOW_RISK_JURISDICTIONS[index % len(LOW_RISK_JURISDICTIONS)]
    flags: list[str] = []
    if jurisdiction in HIGH_RISK_JURISDICTIONS:
        flags.append("high_risk_jurisdiction")
    if index % 5 == 0:
        flags.append("missing_beneficial_owner")
    if index % 6 == 0:
        flags.append("address_mismatch")
    if index % 8 == 0:
        flags.append("ownership_total_incomplete")
    if index % 10 == 0:
        flags.append("signatory_id_expired")
    if index % 12 == 0:
        flags.append("risk_attestation_missing")
    if index % 13 == 0:
        flags.append("sanctions_watchlist_match")

    signatory_expiry_year = 2025 if "signatory_id_expired" in flags else 2032
    registry_fields = {
        "Company Name": company_name,
        "Registration Number": f"REG-{900000 + index}",
        "Incorporation Date": f"201{index % 9}-03-20",
        "Jurisdiction": jurisdiction,
        "Registered Address": address,
    }
    if "missing_beneficial_owner" in flags:
        owner_rows: list[dict[str, Any]] = []
    else:
        owner_rows = [
            {"Owner Name": f"Synthetic Owner {index:02d} A", "Ownership Percent": 55 if "ownership_total_incomplete" not in flags else 35, "Country": jurisdiction},
            {"Owner Name": f"Synthetic Owner {index:02d} B", "Ownership Percent": 45 if "ownership_total_incomplete" not in flags else 20, "Country": "United States"},
        ]
    signatory_fields = {
        "Document Type": "Synthetic Authorized Signatory ID",
        "Full Name": signatory_name,
        "Document Number": f"SIG-{600000 + index}",
        "Expiry Date": f"{signatory_expiry_year}-08-20",
        "Company Name": company_name,
    }
    address_fields = {
        "Company Name": company_name,
        "Business Address": proof_address,
        "Issue Date": "2026-05-04",
        "Document Purpose": "Business Address Proof",
    }
    questionnaire_fields = {
        "Company Name": company_name,
        "Industry": INDUSTRIES[index % len(INDUSTRIES)],
        "Expected Monthly Volume": 75000 + index * 2300,
        "PEP Exposure": "Yes" if index % 9 == 0 else "No",
        "Source Of Funds": "Operating revenue",
    }
    attestation_fields = {
        "Company Name": company_name,
        "Attestation Status": "Missing" if "risk_attestation_missing" in flags else "Complete",
        "Signer": signatory_name,
        "Signature Date": "2026-05-18",
    }

    registry_path = folder / "company_registry.pdf"
    owners_path = folder / "beneficial_ownership.xlsx"
    signatory_path = folder / "authorized_signatory_id.jpg"
    address_path = folder / "business_address_proof.pdf"
    questionnaire_path = folder / "kyb_questionnaire.xlsx"
    attestation_path = folder / "risk_attestation.pdf"
    _write_pdf(registry_path, "Synthetic Company Registry", registry_fields)
    _write_xlsx(owners_path, "beneficial_ownership", owner_rows)
    _write_image(signatory_path, "Synthetic Signatory ID", signatory_fields)
    _write_pdf(address_path, "Synthetic Business Address Proof", address_fields)
    _write_xlsx(questionnaire_path, "kyb_questionnaire", [questionnaire_fields])
    _write_pdf(attestation_path, "Synthetic KYB Risk Attestation", attestation_fields)

    documents = [
        _document(package_id=package_id, document_id=f"{package_id}-REGISTRY", subject_type="business", document_type="company_registry", file_path=registry_path, expected_fields=registry_fields),
        _document(package_id=package_id, document_id=f"{package_id}-OWNERS", subject_type="business", document_type="beneficial_ownership", file_path=owners_path, expected_fields={"Owner Count": len(owner_rows), "Ownership Total": sum(int(row["Ownership Percent"]) for row in owner_rows)}),
        _document(package_id=package_id, document_id=f"{package_id}-SIGNATORY", subject_type="business", document_type="authorized_signatory_id", file_path=signatory_path, expected_fields=signatory_fields, is_image=True, local_fields_hint=signatory_fields),
        _document(package_id=package_id, document_id=f"{package_id}-ADDRESS", subject_type="business", document_type="business_address_proof", file_path=address_path, expected_fields=address_fields),
        _document(package_id=package_id, document_id=f"{package_id}-QUESTIONNAIRE", subject_type="business", document_type="kyb_questionnaire", file_path=questionnaire_path, expected_fields=questionnaire_fields),
        _document(package_id=package_id, document_id=f"{package_id}-ATTESTATION", subject_type="business", document_type="risk_attestation", file_path=attestation_path, expected_fields=attestation_fields),
    ]
    return {
        "package_id": package_id,
        "subject_type": "business",
        "subject_name": company_name,
        "split": _split_for(index),
        "jurisdiction": jurisdiction,
        "address": address,
        "expected_status": _status_from_flags(flags),
        "label_manual_review_required": 1 if flags else 0,
        "expected_risk_score": _risk_from_flags(flags, 0.22 + (index % 6) * 0.02),
        "expected_rule_flags": flags,
        "documents": documents,
    }


def _write_reference_files(packages: list[dict[str, Any]]) -> dict[str, str]:
    reference_root().mkdir(parents=True, exist_ok=True)
    sanctions = {
        "generation_seed": GENERATION_SEED,
        "entries": [
            {"watchlist_id": "SAN-SYN-001", "name": item["subject_name"], "reason": "Synthetic sanctions screening match"}
            for item in packages
            if "sanctions_watchlist_match" in item["expected_rule_flags"]
        ],
    }
    sanctions_watchlist_path().write_text(json.dumps(sanctions, indent=2), encoding="utf-8")
    high_risk_jurisdictions_path().write_text(
        json.dumps({"jurisdictions": HIGH_RISK_JURISDICTIONS}, indent=2),
        encoding="utf-8",
    )
    _write_pdf(
        document_policy_pdf_path(),
        "Synthetic KYC/KYB Document Policy",
        {
            "Reference Date": REFERENCE_DATE.isoformat(),
            "Identity Expiry Rule": "Identity and signatory documents must not be expired.",
            "Address Rule": "Declared address must match proof of address or trigger review.",
            "Ownership Rule": "KYB packages must include beneficial owners and ownership total above 75 percent.",
            "Tax Rule": "Tax certification must be complete before approval.",
        },
        ["This policy is generated for a synthetic local MVP and contains no real compliance guidance."],
    )
    return {
        "sanctions_watchlist": str(sanctions_watchlist_path().resolve()),
        "high_risk_jurisdictions": str(high_risk_jurisdictions_path().resolve()),
        "document_policy_pdf": str(document_policy_pdf_path().resolve()),
    }


def write_artifacts() -> dict[str, str]:
    random.seed(GENERATION_SEED)
    root = kyc_kyb_data_root()
    root.mkdir(parents=True, exist_ok=True)
    _reset_dir(kyc_kyb_raw_root() / "individuals")
    _reset_dir(kyc_kyb_raw_root() / "businesses")
    _reset_dir(reference_root())
    individuals = [_individual_package(index) for index in range(1, INDIVIDUAL_COUNT + 1)]
    businesses = [_business_package(index) for index in range(1, BUSINESS_COUNT + 1)]
    packages = individuals + businesses
    paths = _write_reference_files(packages)
    ground_truth = {
        "generation_seed": GENERATION_SEED,
        "reference_date": REFERENCE_DATE.isoformat(),
        "individual_count": len(individuals),
        "business_count": len(businesses),
        "package_count": len(packages),
        "split_summary": {
            split: {
                "package_count": sum(1 for item in packages if item["split"] == split),
                "manual_review_label_count": sum(item["label_manual_review_required"] for item in packages if item["split"] == split),
            }
            for split in ("train", "val", "test")
        },
        "packages": packages,
        "expected_rule_flags": sorted({flag for item in packages for flag in item["expected_rule_flags"]}),
    }
    ground_truth_path().write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    paths["ground_truth"] = str(ground_truth_path().resolve())
    artifact_paths = [path for path in kyc_kyb_raw_root().rglob("*") if path.is_file()] + [ground_truth_path()]
    checksums = {str(path.resolve().relative_to(root.resolve())).replace("\\", "/"): _checksum(path) for path in artifact_paths}
    metadata = {
        "dataset": "synthetic_kyc_kyb_onboarding_packages",
        "generation_seed": GENERATION_SEED,
        "reference_date": REFERENCE_DATE.isoformat(),
        "individual_count": len(individuals),
        "business_count": len(businesses),
        "package_count": len(packages),
        "document_count": sum(len(item["documents"]) for item in packages),
        "split_summary": ground_truth["split_summary"],
        "hard_rule_types": ground_truth["expected_rule_flags"],
        "artifact_checksums": checksums,
        "description": "Synthetic KYC/KYB onboarding packages with documents, rule flags, and manual review labels.",
    }
    metadata_path().write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    paths["metadata"] = str(metadata_path().resolve())
    paths["raw_root"] = str(kyc_kyb_raw_root().resolve())
    return paths
