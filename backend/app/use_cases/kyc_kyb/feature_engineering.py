from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.use_cases.kyc_kyb.metrics import OPERATIONAL_THRESHOLD
from app.use_cases.kyc_kyb.schemas import KycKybExtractedDocument, KycKybPackageRecord, KycKybRuleFinding

LABEL_COLUMN = "label_manual_review_required"
DROP_FOR_ML = (
    "package_id",
    "subject_name",
    "address",
    "expected_status",
    "expected_rule_flags",
    "failed_rule_ids",
    "missing_documents",
    "field_mismatches",
)
HARD_FAIL_RULES = {
    "required_documents_present",
    "expired_identity_document",
    "missing_tax_certification",
    "signatory_id_expired",
    "missing_beneficial_owner",
    "risk_attestation_missing",
    "sanctions_watchlist_match",
}


def _package_docs(documents: list[KycKybExtractedDocument]) -> dict[str, list[KycKybExtractedDocument]]:
    grouped: dict[str, list[KycKybExtractedDocument]] = {}
    for document in documents:
        grouped.setdefault(document.package_id, []).append(document)
    return grouped


def _package_findings(findings: list[KycKybRuleFinding]) -> dict[str, list[KycKybRuleFinding]]:
    grouped: dict[str, list[KycKybRuleFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.package_id, []).append(finding)
    return grouped


def build_feature_rows(
    packages: list[KycKybPackageRecord],
    documents: list[KycKybExtractedDocument],
    findings: list[KycKybRuleFinding],
) -> list[dict[str, Any]]:
    docs_by_package = _package_docs(documents)
    findings_by_package = _package_findings(findings)
    rows: list[dict[str, Any]] = []
    for package in packages:
        package_docs = docs_by_package.get(package.package_id, [])
        package_findings = findings_by_package.get(package.package_id, [])
        failed = [item for item in package_findings if item.status == "failed"]
        hard_failed = [item for item in failed if item.severity == "hard_fail" or item.rule_id in HARD_FAIL_RULES]
        warnings = [item for item in failed if item.severity == "warning"]
        missing_documents = sorted(
            {
                str(value)
                for item in failed
                for value in item.evidence_fields.get("missing_documents", [])
            }
        )
        if any(item.rule_id == "missing_tax_certification" for item in failed):
            missing_documents.append("tax_certification")
        if any(item.rule_id == "missing_beneficial_owner" for item in failed):
            missing_documents.append("beneficial_ownership")
        if any(item.rule_id == "risk_attestation_missing" for item in failed):
            missing_documents.append("risk_attestation")
        field_mismatches = [
            item.rule_id
            for item in failed
            if item.rule_id in {"address_mismatch", "ownership_total_incomplete"}
        ]
        avg_confidence = (
            sum(document.confidence for document in package_docs) / len(package_docs)
            if package_docs
            else 0.0
        )
        rows.append(
            {
                "package_id": package.package_id,
                "subject_type": package.subject_type,
                "subject_name": package.subject_name,
                "split": package.split,
                "jurisdiction": package.jurisdiction,
                "address": package.address,
                "expected_status": package.expected_status,
                "expected_rule_flags": ";".join(package.expected_rule_flags),
                "failed_rule_ids": ";".join(item.rule_id for item in failed),
                "missing_documents": ";".join(dict.fromkeys(missing_documents)),
                "field_mismatches": ";".join(field_mismatches),
                "document_count": len(package_docs),
                "image_document_count": sum(1 for document in package.documents if document.is_image),
                "fallback_unavailable_count": sum(1 for document in package_docs if document.provider_used == "fallback-unavailable"),
                "gpt4o_fallback_count": sum(1 for document in package_docs if document.provider_used == "gpt-4o-fallback"),
                "average_extraction_confidence": round(avg_confidence, 4),
                "failed_rule_count": len(failed),
                "hard_fail_rule_count": len(hard_failed),
                "warning_rule_count": len(warnings),
                "address_mismatch_flag": int(any(item.rule_id == "address_mismatch" for item in failed)),
                "high_risk_jurisdiction_flag": int(any(item.rule_id == "high_risk_jurisdiction" for item in failed)),
                "sanctions_watchlist_flag": int(any(item.rule_id == "sanctions_watchlist_match" for item in failed)),
                "missing_tax_certification_flag": int(any(item.rule_id == "missing_tax_certification" for item in failed)),
                "missing_beneficial_owner_flag": int(any(item.rule_id == "missing_beneficial_owner" for item in failed)),
                "ownership_total_incomplete_flag": int(any(item.rule_id == "ownership_total_incomplete" for item in failed)),
                "expired_document_flag": int(any(item.rule_id in {"expired_identity_document", "signatory_id_expired"} for item in failed)),
                "label_manual_review_required": package.label_manual_review_required,
            }
        )
    return rows


def prepare_ml_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in DROP_FOR_ML:
        if column in frame.columns:
            frame = frame.drop(columns=[column])
    if "split" in frame.columns:
        frame = frame.drop(columns=["split"])
    return frame


def threshold_file(model_dir: Path) -> Path:
    return Path(model_dir) / "operational_threshold.json"


def save_operational_threshold(model_dir: Path, threshold: float) -> None:
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    threshold_file(model_dir).write_text(json.dumps({"threshold": round(float(threshold), 4)}), encoding="utf-8")


def load_operational_threshold(model_dir: Path) -> float:
    path = threshold_file(model_dir)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("threshold", OPERATIONAL_THRESHOLD))
    return OPERATIONAL_THRESHOLD
