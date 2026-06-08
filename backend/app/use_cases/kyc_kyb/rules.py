from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.use_cases.kyc_kyb.data_generation import REFERENCE_DATE, high_risk_jurisdictions_path, sanctions_watchlist_path
from app.use_cases.kyc_kyb.schemas import KycKybExtractedDocument, KycKybPackageRecord, KycKybRuleFinding


def _docs_by_type(documents: list[KycKybExtractedDocument]) -> dict[str, KycKybExtractedDocument]:
    return {document.document_type: document for document in documents}


def _field(documents: dict[str, KycKybExtractedDocument], document_type: str, field_name: str) -> Any:
    document = documents.get(document_type)
    if document is None:
        return None
    return document.fields.get(field_name)


def _failed(package_id: str, rule_id: str, severity: str, message: str, evidence: dict[str, Any]) -> KycKybRuleFinding:
    return KycKybRuleFinding(
        package_id=package_id,
        rule_id=rule_id,
        severity=severity,
        status="failed",
        message=message,
        evidence_fields=evidence,
    )


def _passed(package_id: str, rule_id: str, message: str, evidence: dict[str, Any]) -> KycKybRuleFinding:
    return KycKybRuleFinding(
        package_id=package_id,
        rule_id=rule_id,
        severity="info",
        status="passed",
        message=message,
        evidence_fields=evidence,
    )


def _date_before(value: Any, comparison: date = REFERENCE_DATE) -> bool:
    try:
        return date.fromisoformat(str(value)) < comparison
    except Exception:
        return False


def _high_risk_jurisdictions() -> set[str]:
    payload = json.loads(high_risk_jurisdictions_path().read_text(encoding="utf-8"))
    return {str(item) for item in payload.get("jurisdictions", [])}


def _sanctions_names() -> set[str]:
    payload = json.loads(sanctions_watchlist_path().read_text(encoding="utf-8"))
    return {str(item.get("name")) for item in payload.get("entries", []) if item.get("name")}


def evaluate_package_rules(
    package: KycKybPackageRecord,
    documents: list[KycKybExtractedDocument],
) -> list[KycKybRuleFinding]:
    docs = _docs_by_type(documents)
    findings: list[KycKybRuleFinding] = []
    missing_document_types = {
        document.document_type
        for document in package.documents
        if document.document_type not in docs or docs[document.document_type].extraction_status == "fallback_unavailable"
    }
    if missing_document_types:
        findings.append(
            _failed(
                package.package_id,
                "required_documents_present",
                "hard_fail",
                "One or more required onboarding documents could not be extracted.",
                {"missing_documents": sorted(missing_document_types)},
            )
        )
    else:
        findings.append(_passed(package.package_id, "required_documents_present", "All required documents were extracted.", {}))

    if package.subject_type == "individual":
        expiry = _field(docs, "id_document_front", "Expiry Date")
        if _date_before(expiry):
            findings.append(_failed(package.package_id, "expired_identity_document", "hard_fail", "Identity document is expired.", {"expiry_date": expiry}))
        else:
            findings.append(_passed(package.package_id, "expired_identity_document", "Identity document is not expired.", {"expiry_date": expiry}))

        proof_address = _field(docs, "proof_of_address", "Address")
        declared_address = _field(docs, "onboarding_form", "Declared Address")
        if proof_address and declared_address and str(proof_address).strip().lower() != str(declared_address).strip().lower():
            findings.append(
                _failed(
                    package.package_id,
                    "address_mismatch",
                    "warning",
                    "Declared address does not match proof of address.",
                    {"proof_address": proof_address, "declared_address": declared_address},
                )
            )
        else:
            findings.append(_passed(package.package_id, "address_mismatch", "Address evidence matches onboarding form.", {"address": proof_address}))

        tax_status = _field(docs, "tax_certification", "Certification Status")
        if str(tax_status).strip().lower() != "complete":
            findings.append(_failed(package.package_id, "missing_tax_certification", "hard_fail", "Tax certification is missing or incomplete.", {"certification_status": tax_status}))
        else:
            findings.append(_passed(package.package_id, "missing_tax_certification", "Tax certification is complete.", {"certification_status": tax_status}))

    if package.subject_type == "business":
        signatory_expiry = _field(docs, "authorized_signatory_id", "Expiry Date")
        if _date_before(signatory_expiry):
            findings.append(_failed(package.package_id, "signatory_id_expired", "hard_fail", "Authorized signatory identity document is expired.", {"expiry_date": signatory_expiry}))
        else:
            findings.append(_passed(package.package_id, "signatory_id_expired", "Authorized signatory identity document is not expired.", {"expiry_date": signatory_expiry}))

        registered_address = _field(docs, "company_registry", "Registered Address")
        proof_address = _field(docs, "business_address_proof", "Business Address")
        if registered_address and proof_address and str(registered_address).strip().lower() != str(proof_address).strip().lower():
            findings.append(
                _failed(
                    package.package_id,
                    "address_mismatch",
                    "warning",
                    "Registered address does not match business address proof.",
                    {"registered_address": registered_address, "business_address": proof_address},
                )
            )
        else:
            findings.append(_passed(package.package_id, "address_mismatch", "Business address evidence matches registry.", {"address": registered_address}))

        owner_count = _field(docs, "beneficial_ownership", "Owner Count") or 0
        ownership_total = _field(docs, "beneficial_ownership", "Ownership Total") or 0
        if float(owner_count) <= 0:
            findings.append(_failed(package.package_id, "missing_beneficial_owner", "hard_fail", "No beneficial owners were supplied.", {"owner_count": owner_count}))
        else:
            findings.append(_passed(package.package_id, "missing_beneficial_owner", "Beneficial owner records are present.", {"owner_count": owner_count}))
        if float(ownership_total) < 75:
            findings.append(_failed(package.package_id, "ownership_total_incomplete", "warning", "Beneficial ownership total is below 75 percent.", {"ownership_total": ownership_total}))
        else:
            findings.append(_passed(package.package_id, "ownership_total_incomplete", "Beneficial ownership total meets policy minimum.", {"ownership_total": ownership_total}))

        attestation_status = _field(docs, "risk_attestation", "Attestation Status")
        if str(attestation_status).strip().lower() != "complete":
            findings.append(_failed(package.package_id, "risk_attestation_missing", "hard_fail", "KYB risk attestation is missing or incomplete.", {"attestation_status": attestation_status}))
        else:
            findings.append(_passed(package.package_id, "risk_attestation_missing", "KYB risk attestation is complete.", {"attestation_status": attestation_status}))

    high_risk = package.jurisdiction in _high_risk_jurisdictions()
    if high_risk:
        findings.append(_failed(package.package_id, "high_risk_jurisdiction", "warning", "Subject jurisdiction is on the synthetic high-risk jurisdiction list.", {"jurisdiction": package.jurisdiction}))
    else:
        findings.append(_passed(package.package_id, "high_risk_jurisdiction", "Subject jurisdiction is not on the synthetic high-risk list.", {"jurisdiction": package.jurisdiction}))

    if package.subject_name in _sanctions_names():
        findings.append(_failed(package.package_id, "sanctions_watchlist_match", "hard_fail", "Subject name matched the synthetic sanctions watchlist.", {"subject_name": package.subject_name}))
    else:
        findings.append(_passed(package.package_id, "sanctions_watchlist_match", "No synthetic sanctions watchlist match found.", {"subject_name": package.subject_name}))
    return findings


def evaluate_all_rules(
    packages: list[KycKybPackageRecord],
    documents: list[KycKybExtractedDocument],
) -> list[KycKybRuleFinding]:
    by_package: dict[str, list[KycKybExtractedDocument]] = {}
    for document in documents:
        by_package.setdefault(document.package_id, []).append(document)
    findings: list[KycKybRuleFinding] = []
    for package in packages:
        findings.extend(evaluate_package_rules(package, by_package.get(package.package_id, [])))
    return findings
