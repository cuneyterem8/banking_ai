from __future__ import annotations

import re
from typing import Any

from app.use_cases.email_automation.schemas import EmailAutomationDraft, EmailComplianceFinding

FULL_IDENTIFIER_PATTERN = re.compile(r"\b(?:ACCT|CARD|SSN|TAX|ID)-?\d{5,}\b", re.IGNORECASE)
MISLEADING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"guaranteed approval",
        r"guaranteed rate",
        r"risk[- ]free",
        r"pre[- ]approved",
        r"no credit check required",
    )
]


def _finding(draft_id: str, rule_id: str, severity: str, status: str, message: str, evidence: dict[str, Any] | None = None) -> EmailComplianceFinding:
    return EmailComplianceFinding(
        draft_id=draft_id,
        rule_id=rule_id,
        severity=severity,
        status=status,
        message=message,
        evidence=evidence or {},
    )


def evaluate_compliance(draft: EmailAutomationDraft) -> tuple[EmailAutomationDraft, list[EmailComplianceFinding]]:
    text = " ".join([draft.subject, draft.preheader, draft.body, draft.call_to_action, " ".join(draft.required_disclosures)])
    findings: list[EmailComplianceFinding] = []

    identifier_matches = FULL_IDENTIFIER_PATTERN.findall(text)
    findings.append(
        _finding(
            draft.draft_id,
            "no_full_identifier",
            "critical",
            "failed" if identifier_matches else "passed",
            "Draft must not include full sensitive identifiers.",
            {"matches": identifier_matches[:5]},
        )
    )

    misleading = [pattern.pattern for pattern in MISLEADING_PATTERNS if pattern.search(text)]
    findings.append(
        _finding(
            draft.draft_id,
            "no_misleading_claim",
            "critical",
            "failed" if misleading else "passed",
            "Draft must not include guaranteed approval, guaranteed rates, or risk-free claims.",
            {"patterns": misleading},
        )
    )

    has_cta = bool(draft.call_to_action.strip())
    findings.append(
        _finding(
            draft.draft_id,
            "has_call_to_action",
            "warning",
            "passed" if has_cta else "failed",
            "Draft must include a clear call to action.",
            {"call_to_action": draft.call_to_action},
        )
    )

    missing_disclosures = (
        [
            disclosure
            for disclosure in draft.required_disclosures
            if disclosure.lower() not in text.lower()
        ]
        if draft.required_disclosures
        else ["required disclosure"]
    )
    findings.append(
        _finding(
            draft.draft_id,
            "required_disclosure_present",
            "warning",
            "failed" if missing_disclosures else "passed",
            "Draft must include required disclosures.",
            {"missing_disclosures": missing_disclosures},
        )
    )

    opt_out_present = "opt out" in text.lower() or "unsubscribe" in text.lower()
    opt_out_failed = draft.communication_type == "campaign" and not opt_out_present
    findings.append(
        _finding(
            draft.draft_id,
            "marketing_opt_out",
            "warning",
            "failed" if opt_out_failed else "passed",
            "Marketing drafts must include opt-out language.",
            {"communication_type": draft.communication_type, "opt_out_present": opt_out_present},
        )
    )

    failed = [item for item in findings if item.status == "failed"]
    critical_failed = [item for item in failed if item.severity == "critical"]
    if critical_failed:
        compliance_status = "Rejected"
        risk_level = "Critical"
    elif failed:
        compliance_status = "Needs Review"
        risk_level = "High" if len(failed) > 1 else "Medium"
    else:
        compliance_status = "Approved"
        risk_level = "Low"
    updated = draft.model_copy(
        update={
            "compliance_status": compliance_status,
            "risk_level": risk_level,
            "validation_issues": [item.message for item in failed],
        }
    )
    return updated, findings
