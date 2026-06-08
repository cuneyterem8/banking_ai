from pydantic import BaseModel, Field


class AmlAlertRecord(BaseModel):
    alert_id: str
    customer_id: str
    account_id: str
    entity_id: str
    kyc_risk_score: float = Field(ge=0, le=1)
    jurisdiction_risk_score: float = Field(ge=0, le=1)
    sanctions_name_similarity: float = Field(ge=0, le=1)
    adverse_media_flag: int = Field(ge=0, le=1)
    prior_alert_count_12m: int
    cash_deposit_total_30d: float
    outgoing_wire_total_30d: float
    round_amount_ratio: float = Field(ge=0, le=1)
    rapid_movement_ratio: float = Field(ge=0, le=1)
    structuring_count_7d: int
    unusual_hours_count: int
    counterparty_cluster_risk: float = Field(ge=0, le=1)
    network_degree: int
    network_centrality_score: float = Field(ge=0, le=1)
    nested_entity_depth: int
    beneficial_owner_mismatch: int = Field(ge=0, le=1)
    alert_type: str
    typology_tag: str
    rule_triggers: str
    linked_transaction_count: int
    related_entities: str
    label_sar_recommended: int = Field(ge=0, le=1)


class AmlAlertDecision(BaseModel):
    alert_id: str
    customer_id: str
    account_id: str
    typology_tag: str
    sar_probability: float = Field(ge=0, le=1)
    risk_level: str
    predicted_sar_recommended: int = Field(ge=0, le=1)
    actual_sar_recommended: int = Field(ge=0, le=1)
    decision: str
    top_factors: list[str]
    related_entities: list[str]
    linked_transaction_count: int
    provider_used: str = "local-autogluon"


class AmlNarrativeDraft(BaseModel):
    narrative_status: str
    alert_id: str
    summary: str
    suspicious_activity_type: str
    evidence_bullets: list[str]
    recommended_next_steps: list[str]
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    provider_used: str
    model_name: str
    warnings: list[str] = Field(default_factory=list)


class AmlNetworkSummary(BaseModel):
    account_count: int
    counterparty_count: int
    transaction_count: int
    alert_link_count: int
    entity_count: int
    cluster_count: int
    high_risk_cluster_count: int
    high_risk_jurisdictions: list[str]
    top_clusters: list[dict]


class AmlCaseNoteSummary(BaseModel):
    file_name: str
    note_count: int
    escalation_topic_count: int
    guidance_excerpt: str


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


class AmlSplitEvaluation(BaseModel):
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
    records: list[AmlAlertDecision]


class AmlMonitoringSummary(BaseModel):
    split: str
    alert_count: int
    sar_label_count: int
    high_risk_count: int
    critical_risk_count: int
    narrative_count: int
    fallback_count: int
    timeout_count: int
    invalid_json_count: int
    warning_count: int
    average_sar_probability: float
    provider_used: str
    model_name: str
    primary_score: float | None = None
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float | None = None
    threshold: float


class AmlMonitoringPayload(BaseModel):
    split: str
    summary: AmlMonitoringSummary
    evaluation: AmlSplitEvaluation
    alerts: list[AmlAlertDecision]
    narratives: list[AmlNarrativeDraft]
    network_summary: AmlNetworkSummary
    case_note_summary: AmlCaseNoteSummary
    warnings: list[str] = Field(default_factory=list)
