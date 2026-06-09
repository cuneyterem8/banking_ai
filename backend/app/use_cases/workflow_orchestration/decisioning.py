from __future__ import annotations

from app.use_cases.workflow_orchestration.schemas import (
    WorkflowCase,
    WorkflowCaseResult,
    WorkflowDependencySnapshot,
    WorkflowRoutingDecision,
    WorkflowSlaResult,
    WorkflowStepResult,
)


BASE_OWNER_BY_WORKFLOW = {
    "retail_account_opening": "Retail Onboarding Team",
    "smb_lending_onboarding": "SMB Credit Operations",
    "card_dispute_escalation": "Card Disputes Desk",
    "cash_liquidity_exception": "Treasury Operations",
}


def risk_level(score: float) -> str:
    if score >= 0.86:
        return "Critical"
    if score >= 0.66:
        return "High"
    if score >= 0.38:
        return "Medium"
    return "Low"


def dependency_status(snapshots: list[WorkflowDependencySnapshot]) -> str:
    if not snapshots:
        return "Missing"
    available = sum(1 for item in snapshots if item.status == "available")
    if available == len(snapshots):
        return "Ready"
    if available:
        return "Partial"
    return "Missing"


def _status_and_owner(case: WorkflowCase, dep_status: str) -> tuple[str, str]:
    base_owner = BASE_OWNER_BY_WORKFLOW[case.workflow_type]
    if "identity_mismatch" in case.blockers:
        return "Rejected", "Risk Review Committee"
    if "incomplete_documents" in case.blockers or "missing_dependency_evidence" in case.blockers:
        return "Blocked", "Intake Operations"
    if dep_status == "Missing":
        return "Blocked", "Intake Operations"
    if case.risk_score >= 0.86:
        return "Escalated", "Case Escalation Team"
    if case.risk_score >= 0.42 or case.blockers or dep_status == "Partial":
        return "Needs Review", base_owner
    return "Straight Through Approved", base_owner


def _next_actions(final_status: str, case: WorkflowCase, dep_status: str) -> list[str]:
    if final_status == "Straight Through Approved":
        return ["Complete automated checklist", "Notify the synthetic relationship owner"]
    if final_status == "Rejected":
        return ["Record rejection reason", "Send compliant synthetic notice", "Close the workflow case"]
    if final_status == "Blocked":
        actions = ["Request missing evidence", "Pause SLA clock after intake review", "Reopen when blockers are resolved"]
        if dep_status != "Ready":
            actions.insert(0, "Review missing dependency outputs")
        return actions
    if final_status == "Escalated":
        return ["Assign escalation owner", "Prepare supervisor review package", "Track same-day follow-up"]
    return [
        "Assign manual review queue",
        f"Validate {case.workflow_type.replace('_', ' ')} evidence",
        "Update next action before SLA due time",
    ]


def _top_reasons(
    case: WorkflowCase,
    steps: list[WorkflowStepResult],
    dep_snapshots: list[WorkflowDependencySnapshot],
) -> list[str]:
    reasons = [f"Risk score {case.risk_score:.3f} maps to {risk_level(case.risk_score)} risk."]
    reasons.extend(f"Blocker: {blocker.replace('_', ' ')}." for blocker in case.blockers)
    missing = [item.use_case_slug for item in dep_snapshots if item.status != "available"]
    if missing:
        reasons.append(f"Missing dependency outputs: {', '.join(missing)}.")
    warning_steps = [step.step_id for step in steps if step.status != "completed"]
    if warning_steps:
        reasons.append(f"Workflow steps with warnings: {', '.join(warning_steps)}.")
    return list(dict.fromkeys(reasons))[:6]


def evaluate_sla(case: WorkflowCase, final_status: str) -> WorkflowSlaResult:
    if final_status in {"Blocked", "Rejected"} or "sla_breach_risk" in case.blockers:
        elapsed = case.sla_hours + (4 if case.priority == "Urgent" else 8)
    elif final_status == "Escalated":
        elapsed = max(1, case.sla_hours - 1)
    elif final_status == "Needs Review":
        elapsed = max(1, case.sla_hours - 3)
    else:
        elapsed = max(1, case.sla_hours * 0.35)
    remaining = round(case.sla_hours - elapsed, 2)
    if remaining < 0:
        status = "Breached"
        reason = "Elapsed orchestration time exceeds the synthetic SLA policy."
    elif remaining <= 2:
        status = "At Risk"
        reason = "Case is close to the synthetic SLA deadline."
    else:
        status = "On Track"
        reason = None
    return WorkflowSlaResult(
        case_id=case.case_id,
        policy_hours=case.sla_hours,
        elapsed_hours=round(elapsed, 2),
        remaining_hours=remaining,
        sla_status=status,
        breach_reason=reason,
    )


def route_case(
    case: WorkflowCase,
    steps: list[WorkflowStepResult],
    dependency_snapshots: list[WorkflowDependencySnapshot],
) -> tuple[WorkflowCaseResult, WorkflowRoutingDecision, WorkflowSlaResult]:
    dep_status = dependency_status(dependency_snapshots)
    final_status, owner = _status_and_owner(case, dep_status)
    level = risk_level(case.risk_score)
    top_reasons = _top_reasons(case, steps, dependency_snapshots)
    next_actions = _next_actions(final_status, case, dep_status)
    straight_through = final_status == "Straight Through Approved" and dep_status == "Ready"
    manual_review = final_status in {"Needs Review", "Escalated", "Blocked", "Rejected"}
    routing = WorkflowRoutingDecision(
        case_id=case.case_id,
        final_status=final_status,
        recommended_owner=owner,
        risk_level=level,
        straight_through_eligible=straight_through,
        manual_review_required=manual_review,
        dependency_status=dep_status,
        top_reasons=top_reasons,
        next_best_actions=next_actions,
    )
    result = WorkflowCaseResult(
        case_id=case.case_id,
        workflow_type=case.workflow_type,
        subject_id=case.subject_id,
        subject_name=case.subject_name,
        priority=case.priority,
        final_status=final_status,
        risk_level=level,
        straight_through_eligible=straight_through,
        manual_review_required=manual_review,
        recommended_owner=owner,
        next_best_actions=next_actions,
        top_reasons=top_reasons,
        dependency_status=dep_status,
        provider_used="local-orchestrator",
        input_context={
            "requested_product": case.requested_product,
            "region": case.region,
            "risk_score": case.risk_score,
            "risk_signals": case.risk_signals,
            "transaction_context": case.transaction_context,
            "communications_context": case.communications_context,
            "blockers": case.blockers,
        },
    )
    return result, routing, evaluate_sla(case, final_status)
