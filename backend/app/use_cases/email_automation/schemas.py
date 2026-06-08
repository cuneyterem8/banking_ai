from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CustomerProfile(BaseModel):
    customer_id: str
    first_name: str
    segment: str
    lifecycle_stage: str
    preferred_channel: str
    synthetic_email: str
    masked_account: str
    locale: str
    marketing_opt_in: bool


class CustomerEvent(BaseModel):
    event_id: str
    customer_id: str
    event_type: str
    event_date: str
    product_name: str
    masked_account: str
    amount_due: float | None = None
    due_date: str | None = None
    branch_name: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class CampaignRecord(BaseModel):
    audience_id: str
    campaign_id: str
    campaign_name: str
    campaign_type: str
    customer_id: str
    segment: str
    offer_summary: str
    required_disclosure: str
    opt_out_required: bool = True


class EmailTemplate(BaseModel):
    template_key: str
    communication_type: str
    subject: str
    preheader: str
    body: str
    call_to_action: str
    required_disclosures: list[str] = Field(default_factory=list)


class EmailGenerationCase(BaseModel):
    case_id: str
    communication_type: str
    customer_id: str
    event_id: str | None = None
    event_type: str | None = None
    campaign_id: str | None = None
    audience_id: str | None = None
    template_key: str
    custom_context: str = ""
    expected_required_disclosures: list[str] = Field(default_factory=list)


class EmailDraftRequest(BaseModel):
    customer_id: str
    communication_type: str
    event_type: str | None = None
    campaign_id: str | None = None
    custom_context: str = ""


class EmailAutomationDraft(BaseModel):
    draft_id: str
    case_id: str
    customer_id: str
    communication_type: str
    event_type: str | None = None
    campaign_id: str | None = None
    subject: str
    preheader: str
    body: str
    call_to_action: str
    provider_used: str
    model_name: str
    generation_status: str
    confidence: float = Field(ge=0, le=1)
    compliance_status: str
    risk_level: str
    required_disclosures: list[str] = Field(default_factory=list)
    personalization_used: list[str] = Field(default_factory=list)
    tone_tags: list[str] = Field(default_factory=list)
    validation_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EmailComplianceFinding(BaseModel):
    draft_id: str
    rule_id: str
    severity: str
    status: str
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class EmailAutomationScore(BaseModel):
    draft_id: str
    quality_score: float = Field(ge=0, le=1)
    compliance_score: float = Field(ge=0, le=1)
    personalization_score: float = Field(ge=0, le=1)
    readability_score: float = Field(ge=0, le=1)


class EmailAutomationSummary(BaseModel):
    mode: str
    draft_count: int
    service_draft_count: int
    campaign_draft_count: int
    approved_count: int
    needs_review_count: int
    rejected_count: int
    fallback_count: int
    timeout_count: int
    invalid_json_count: int
    warning_count: int
    average_quality_score: float
    approval_rate: float
    provider_used: str
    model_name: str


class EmailAutomationPayload(BaseModel):
    mode: str
    summary: EmailAutomationSummary
    drafts: list[EmailAutomationDraft]
    compliance_findings: list[EmailComplianceFinding]
    scores: list[EmailAutomationScore]
    warnings: list[str] = Field(default_factory=list)
