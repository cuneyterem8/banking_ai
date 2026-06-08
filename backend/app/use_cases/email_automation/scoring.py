from __future__ import annotations

from app.use_cases.email_automation.schemas import EmailAutomationDraft, EmailAutomationScore, EmailComplianceFinding


def score_draft(draft: EmailAutomationDraft, findings: list[EmailComplianceFinding]) -> EmailAutomationScore:
    failed = [item for item in findings if item.status == "failed"]
    critical = [item for item in failed if item.severity == "critical"]
    compliance_score = max(0.0, 1.0 - len(failed) * 0.18 - len(critical) * 0.32)
    personalization_score = min(1.0, 0.25 + len(draft.personalization_used) * 0.18)
    word_count = len(draft.body.split())
    readability_score = 1.0 if 35 <= word_count <= 130 else 0.72
    quality_score = round((compliance_score * 0.5) + (personalization_score * 0.25) + (readability_score * 0.25), 4)
    return EmailAutomationScore(
        draft_id=draft.draft_id,
        quality_score=quality_score,
        compliance_score=round(compliance_score, 4),
        personalization_score=round(personalization_score, 4),
        readability_score=round(readability_score, 4),
    )
