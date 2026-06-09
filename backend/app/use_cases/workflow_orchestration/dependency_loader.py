from __future__ import annotations

from sqlmodel import Session, desc, select

from app.db.models import ModelRun, ProcessedResult
from app.use_cases.registry import USE_CASES
from app.use_cases.workflow_orchestration.schemas import WorkflowDependencySnapshot

DEPENDENCY_SLUGS = tuple(item.slug for item in USE_CASES if item.implementation_order <= 9)
DEPENDENCY_TITLES = {item.slug: item.title for item in USE_CASES}


def load_dependency_snapshots(session: Session) -> list[WorkflowDependencySnapshot]:
    snapshots: list[WorkflowDependencySnapshot] = []
    for slug in DEPENDENCY_SLUGS:
        result = session.exec(
            select(ProcessedResult)
            .where(ProcessedResult.use_case_slug == slug)
            .order_by(desc(ProcessedResult.created_at))
            .limit(1)
        ).first()
        if result is None:
            snapshots.append(
                WorkflowDependencySnapshot(
                    use_case_slug=slug,
                    title=DEPENDENCY_TITLES.get(slug, slug),
                    status="missing",
                    warning=f"No persisted result is available for {slug}; synthetic fallback evidence will be used.",
                )
            )
            continue
        run = session.get(ModelRun, result.run_id)
        if run is None or run.status != "completed":
            snapshots.append(
                WorkflowDependencySnapshot(
                    use_case_slug=slug,
                    title=DEPENDENCY_TITLES.get(slug, slug),
                    status="failed",
                    latest_result_id=result.id,
                    result_type=result.result_type,
                    warning=f"Latest result for {slug} does not have a completed model run.",
                )
            )
            continue
        payload_summary = {}
        if isinstance(result.payload, dict):
            raw_summary = result.payload.get("summary") or result.payload.get("evaluation") or {}
            payload_summary = raw_summary if isinstance(raw_summary, dict) else {}
        snapshots.append(
            WorkflowDependencySnapshot(
                use_case_slug=slug,
                title=DEPENDENCY_TITLES.get(slug, slug),
                status="available",
                latest_run_id=run.id,
                latest_result_id=result.id,
                result_type=result.result_type,
                provider_used=run.provider_used,
                summary=payload_summary,
            )
        )
    return snapshots


def snapshots_for_case(
    case_dependency_slugs: list[str],
    snapshots: list[WorkflowDependencySnapshot],
) -> list[WorkflowDependencySnapshot]:
    by_slug = {item.use_case_slug: item for item in snapshots}
    return [
        by_slug.get(
            slug,
            WorkflowDependencySnapshot(
                use_case_slug=slug,
                title=DEPENDENCY_TITLES.get(slug, slug),
                status="missing",
                warning=f"Required dependency {slug} is not known to the orchestration registry.",
            ),
        )
        for slug in case_dependency_slugs
    ]
