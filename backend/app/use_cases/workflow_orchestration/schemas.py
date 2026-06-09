from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowType = Literal[
    "retail_account_opening",
    "smb_lending_onboarding",
    "card_dispute_escalation",
    "cash_liquidity_exception",
]
Priority = Literal["Standard", "Elevated", "Urgent"]
RiskLevel = Literal["Low", "Medium", "High", "Critical"]
FinalStatus = Literal[
    "Straight Through Approved",
    "Needs Review",
    "Escalated",
    "Blocked",
    "Rejected",
]
WorkflowMode = Literal["startup_evaluation", "case_run"]


class WorkflowCase(BaseModel):
    case_id: str
    workflow_type: WorkflowType
    subject_id: str
    subject_name: str
    priority: Priority
    region: str
    requested_product: str
    created_at: str
    sla_hours: int
    dependency_slugs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    risk_score: float = Field(ge=0, le=1)
    risk_signals: dict[str, Any] = Field(default_factory=dict)
    expected_owner: str
    expected_final_status: FinalStatus
    expected_next_actions: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    transaction_context: dict[str, Any] = Field(default_factory=dict)
    communications_context: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinitionStep(BaseModel):
    step_id: str
    title: str
    owner: str
    depends_on: list[str] = Field(default_factory=list)
    required_dependencies: list[str] = Field(default_factory=list)
    sla_minutes: int = 15


class WorkflowDefinition(BaseModel):
    workflow_type: WorkflowType
    title: str
    description: str
    steps: list[WorkflowDefinitionStep]


class WorkflowDependencySnapshot(BaseModel):
    use_case_slug: str
    title: str
    status: Literal["available", "missing", "failed"]
    latest_run_id: str | None = None
    latest_result_id: str | None = None
    result_type: str | None = None
    provider_used: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    warning: str | None = None


class WorkflowStepResult(BaseModel):
    step_id: str
    case_id: str
    workflow_type: WorkflowType
    title: str
    owner: str
    depends_on: list[str] = Field(default_factory=list)
    status: Literal["completed", "completed_with_warning", "blocked"]
    required_dependencies: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class WorkflowRoutingDecision(BaseModel):
    case_id: str
    final_status: FinalStatus
    recommended_owner: str
    risk_level: RiskLevel
    straight_through_eligible: bool
    manual_review_required: bool
    dependency_status: Literal["Ready", "Partial", "Missing"]
    top_reasons: list[str] = Field(default_factory=list)
    next_best_actions: list[str] = Field(default_factory=list)


class WorkflowSlaResult(BaseModel):
    case_id: str
    policy_hours: int
    elapsed_hours: float
    remaining_hours: float
    sla_status: Literal["On Track", "At Risk", "Breached"]
    breach_reason: str | None = None


class WorkflowCaseResult(BaseModel):
    case_id: str
    workflow_type: WorkflowType
    subject_id: str
    subject_name: str
    priority: Priority
    final_status: FinalStatus
    risk_level: RiskLevel
    straight_through_eligible: bool
    manual_review_required: bool
    recommended_owner: str
    next_best_actions: list[str] = Field(default_factory=list)
    top_reasons: list[str] = Field(default_factory=list)
    dependency_status: Literal["Ready", "Partial", "Missing"]
    provider_used: str
    input_context: dict[str, Any] = Field(default_factory=dict)


class WorkflowCaseSummary(BaseModel):
    case_id: str
    summary_status: str
    summary: str
    recommended_wording: str
    next_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    provider_used: str
    model_name: str
    warnings: list[str] = Field(default_factory=list)


class WorkflowOrchestrationSummary(BaseModel):
    mode: WorkflowMode
    case_count: int
    workflow_type_count: int
    straight_through_count: int
    needs_review_count: int
    escalated_count: int
    blocked_count: int
    rejected_count: int
    dependency_ready_count: int
    dependency_warning_count: int
    sla_breach_count: int
    average_risk_score: float
    summary_count: int
    fallback_count: int
    timeout_count: int
    invalid_json_count: int
    warning_count: int
    provider_used: str
    model_name: str


class WorkflowOrchestrationPayload(BaseModel):
    mode: WorkflowMode
    summary: WorkflowOrchestrationSummary
    cases: list[WorkflowCaseResult]
    workflow_steps: list[WorkflowStepResult]
    dependency_snapshots: list[WorkflowDependencySnapshot]
    routing_decisions: list[WorkflowRoutingDecision]
    case_summaries: list[WorkflowCaseSummary]
    sla_results: list[WorkflowSlaResult]
    warnings: list[str] = Field(default_factory=list)


class WorkflowOrchestrationRequest(BaseModel):
    case_id: str
    include_llm_summary: bool = True
