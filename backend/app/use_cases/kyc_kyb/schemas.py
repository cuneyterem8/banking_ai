from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KycKybDocumentManifest(BaseModel):
    document_id: str
    package_id: str
    subject_type: str
    document_type: str
    file_name: str
    relative_path: str
    is_image: bool = False
    expected_fields: dict[str, Any] = Field(default_factory=dict)
    local_fields_hint: dict[str, Any] = Field(default_factory=dict)


class KycKybPackageRecord(BaseModel):
    package_id: str
    subject_type: str
    subject_name: str
    split: str
    jurisdiction: str
    address: str
    expected_status: str
    label_manual_review_required: int = Field(ge=0, le=1)
    expected_risk_score: float = Field(ge=0, le=1)
    expected_rule_flags: list[str] = Field(default_factory=list)
    documents: list[KycKybDocumentManifest] = Field(default_factory=list)


class KycKybExtractedDocument(BaseModel):
    package_id: str
    document_id: str
    document_type: str
    file_name: str
    provider_used: str
    extraction_status: str
    confidence: float = Field(ge=0, le=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    validation_issues: list[str] = Field(default_factory=list)
    raw_text_excerpt: str = ""


class KycKybRuleFinding(BaseModel):
    package_id: str
    rule_id: str
    severity: str
    status: str
    message: str
    evidence_fields: dict[str, Any] = Field(default_factory=dict)


class KycKybPackageDecision(BaseModel):
    package_id: str
    subject_type: str
    subject_name: str
    verification_status: str
    risk_score: float = Field(ge=0, le=1)
    risk_level: str
    manual_review_required: int = Field(ge=0, le=1)
    actual_manual_review_required: int = Field(ge=0, le=1)
    hard_rule_triggered: bool
    top_factors: list[str]
    missing_documents: list[str]
    field_mismatches: list[str]
    provider_used: str


class ConfusionMatrix(BaseModel):
    tp: int
    tn: int
    fp: int
    fn: int


class RocPoint(BaseModel):
    threshold: float
    tpr: float
    fpr: float


class PrPoint(BaseModel):
    threshold: float
    precision: float
    recall: float


class KycKybSplitEvaluation(BaseModel):
    split: str
    record_count: int
    primary_metric: str
    primary_metric_label: str
    primary_score: float | None = None
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float | None = None
    threshold: float
    correct_predictions: int
    confusion_matrix: ConfusionMatrix
    pr_curve: list[PrPoint]
    roc_curve: list[RocPoint]
    records: list[KycKybPackageDecision]


class KycKybSummary(BaseModel):
    split: str
    package_count: int
    individual_count: int
    business_count: int
    manual_review_label_count: int
    needs_review_count: int
    rejected_count: int
    hard_rule_count: int
    extracted_document_count: int
    fallback_count: int
    warning_count: int
    average_risk_score: float
    provider_used: str
    model_name: str
    primary_score: float | None = None
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float | None = None
    threshold: float


class KycKybPayload(BaseModel):
    split: str
    summary: KycKybSummary
    evaluation: KycKybSplitEvaluation
    packages: list[KycKybPackageRecord]
    extracted_documents: list[KycKybExtractedDocument]
    rule_findings: list[KycKybRuleFinding]
    risk_decisions: list[KycKybPackageDecision]
    warnings: list[str] = Field(default_factory=list)
