from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.use_cases.workflow_orchestration.data_generation import (
    CASE_COUNT,
    HELDOUT_CASE_COUNT,
    STARTUP_CASE_COUNT,
    case_dir,
    dependency_contracts_path,
    ground_truth_path,
    heldout_cases_path,
    metadata_path,
    sla_policy_path,
    startup_cases_path,
    workflow_data_root,
    workflow_definitions_path,
    workflow_raw_root,
    write_artifacts,
)
from app.use_cases.workflow_orchestration.schemas import WorkflowCase, WorkflowDefinition

USE_CASE_SLUG = "workflow-orchestration"
DATASET_KEY_WORKFLOW_CASES = "workflow_cases"


def ensure_raw_artifacts() -> None:
    required = [
        workflow_definitions_path(),
        sla_policy_path(),
        dependency_contracts_path(),
        startup_cases_path(),
        heldout_cases_path(),
        metadata_path(),
        ground_truth_path(),
    ]
    if not all(path.exists() for path in required):
        write_artifacts()
        return
    manifest = load_manifest(regenerate_if_missing=False)
    if (
        manifest.get("case_count") != CASE_COUNT
        or manifest.get("startup_case_count") != STARTUP_CASE_COUNT
        or manifest.get("heldout_case_count") != HELDOUT_CASE_COUNT
    ):
        write_artifacts()


def load_manifest(*, regenerate_if_missing: bool = True) -> dict[str, Any]:
    if regenerate_if_missing and not metadata_path().exists():
        write_artifacts()
    return json.loads(metadata_path().read_text(encoding="utf-8"))


def load_ground_truth(*, regenerate_if_missing: bool = True) -> dict[str, Any]:
    if regenerate_if_missing:
        ensure_raw_artifacts()
    return json.loads(ground_truth_path().read_text(encoding="utf-8"))


def load_workflow_definitions() -> list[WorkflowDefinition]:
    ensure_raw_artifacts()
    return [WorkflowDefinition(**item) for item in json.loads(workflow_definitions_path().read_text(encoding="utf-8"))]


def load_case_profiles() -> list[WorkflowCase]:
    ensure_raw_artifacts()
    cases: list[WorkflowCase] = []
    for path in sorted((workflow_raw_root() / "cases").glob("case_*/case_profile.json")):
        cases.append(WorkflowCase(**json.loads(path.read_text(encoding="utf-8"))))
    return cases


def load_case_profile(case_id: str) -> WorkflowCase:
    ensure_raw_artifacts()
    path = case_dir(case_id) / "case_profile.json"
    if not path.exists():
        raise KeyError(f"Synthetic workflow case not found: {case_id}")
    return WorkflowCase(**json.loads(path.read_text(encoding="utf-8")))


def _load_case_id_file(path: Path) -> list[str]:
    ensure_raw_artifacts()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(item) for item in payload.get("case_ids", [])]


def load_startup_case_ids() -> list[str]:
    return _load_case_id_file(startup_cases_path())


def load_heldout_case_ids() -> list[str]:
    return _load_case_id_file(heldout_cases_path())


def load_cases_by_ids(case_ids: list[str]) -> list[WorkflowCase]:
    by_id = {case.case_id: case for case in load_case_profiles()}
    return [by_id[case_id] for case_id in case_ids if case_id in by_id]


def manifest_preview(limit: int = 16) -> list[dict[str, Any]]:
    return [
        {
            "case_id": case.case_id,
            "workflow_type": case.workflow_type,
            "subject_name": case.subject_name,
            "priority": case.priority,
            "expected_status": case.expected_final_status,
            "dependency_count": len(case.dependency_slugs),
        }
        for case in load_case_profiles()[:limit]
    ]


def ground_truth_summary() -> dict[str, Any]:
    ground_truth = load_ground_truth()
    cases = ground_truth.get("cases", [])
    status_counts: dict[str, int] = {}
    for item in cases:
        status = str(item.get("expected_final_status", "Unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "case_count": ground_truth["case_count"],
        "startup_case_count": ground_truth["startup_case_count"],
        "heldout_case_count": ground_truth["heldout_case_count"],
        "workflow_types": ground_truth["workflow_types"],
        "expected_status_counts": status_counts,
    }


def raw_artifact_paths() -> list[Path]:
    ensure_raw_artifacts()
    return sorted(path for path in workflow_raw_root().rglob("*") if path.is_file()) + [metadata_path(), ground_truth_path()]


def workflow_data_relative(path: Path) -> str:
    return str(path.resolve().relative_to(workflow_data_root().resolve())).replace("\\", "/")
