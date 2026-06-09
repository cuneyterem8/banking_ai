from __future__ import annotations

from app.use_cases.workflow_orchestration.schemas import (
    WorkflowCase,
    WorkflowDefinition,
    WorkflowDependencySnapshot,
    WorkflowStepResult,
)


def _dependency_status(required: list[str], snapshots: list[WorkflowDependencySnapshot]) -> tuple[str, list[str]]:
    by_slug = {snapshot.use_case_slug: snapshot for snapshot in snapshots}
    missing = [
        slug
        for slug in required
        if by_slug.get(slug) is None or by_slug[slug].status != "available"
    ]
    if missing:
        return "completed_with_warning", [f"Missing dependency output: {slug}" for slug in missing]
    return "completed", []


def execute_workflow_case(
    case: WorkflowCase,
    definition: WorkflowDefinition,
    dependency_snapshots: list[WorkflowDependencySnapshot],
) -> list[WorkflowStepResult]:
    results: list[WorkflowStepResult] = []
    completed_step_ids: set[str] = set()
    for index, step in enumerate(definition.steps, start=1):
        unmet_steps = [step_id for step_id in step.depends_on if step_id not in completed_step_ids]
        status, warnings = _dependency_status(step.required_dependencies, dependency_snapshots)
        blockers = list(warnings)
        if unmet_steps:
            status = "blocked"
            blockers.extend(f"Prior step did not complete: {step_id}" for step_id in unmet_steps)
        if case.blockers and step.step_id in {"document_check", "kyc_decision", "kyb_review", "policy_review", "risk_context"}:
            status = "completed_with_warning" if status == "completed" else status
            blockers.extend(case.blockers)
        evidence = [
            f"Case priority: {case.priority}",
            f"Risk score: {case.risk_score:.3f}",
            f"Required dependencies: {', '.join(step.required_dependencies) or 'none'}",
        ]
        results.append(
            WorkflowStepResult(
                step_id=step.step_id,
                case_id=case.case_id,
                workflow_type=case.workflow_type,
                title=step.title,
                owner=step.owner,
                depends_on=step.depends_on,
                status=status,
                required_dependencies=step.required_dependencies,
                evidence=evidence,
                blockers=list(dict.fromkeys(blockers)),
                duration_ms=step.sla_minutes * 100 + index * 17,
            )
        )
        if status != "blocked":
            completed_step_ids.add(step.step_id)
    return results
