import json
from pathlib import Path
from typing import Any

from app.use_cases.support_chatbot.data_generation import (
    ground_truth_path,
    metadata_path,
    support_data_root,
    support_raw_root,
    write_artifacts,
)
from app.use_cases.support_chatbot.schemas import SupportDocumentManifest, SupportEvaluationCase

USE_CASE_SLUG = "support-chatbot"
DATASET_KEY_KNOWLEDGE_BASE = "knowledge_base"


def support_questions_path() -> Path:
    return support_raw_root() / "evaluation" / "support_questions.json"


def ensure_raw_artifacts() -> None:
    required = [metadata_path(), ground_truth_path(), support_questions_path()]
    if not all(path.exists() for path in required):
        write_artifacts()
        return
    manifest = load_manifest(regenerate_if_missing=False)
    if not manifest.get("documents"):
        write_artifacts()
        return
    for item in manifest["documents"]:
        if not (support_data_root() / item["relative_path"]).exists():
            write_artifacts()
            return


def load_manifest(*, regenerate_if_missing: bool = True) -> dict[str, Any]:
    if regenerate_if_missing and not metadata_path().exists():
        write_artifacts()
    return json.loads(metadata_path().read_text(encoding="utf-8"))


def load_ground_truth() -> dict[str, Any]:
    ensure_raw_artifacts()
    return json.loads(ground_truth_path().read_text(encoding="utf-8"))


def load_support_questions() -> list[dict[str, str]]:
    ensure_raw_artifacts()
    return json.loads(support_questions_path().read_text(encoding="utf-8"))


def load_evaluation_cases() -> list[SupportEvaluationCase]:
    ground_truth = load_ground_truth()
    return [SupportEvaluationCase(**item) for item in ground_truth["evaluation_cases"]]


def load_document_manifest() -> list[SupportDocumentManifest]:
    ensure_raw_artifacts()
    manifest = load_manifest()
    return [SupportDocumentManifest(**item) for item in manifest["documents"]]


def raw_artifact_paths() -> list[Path]:
    ensure_raw_artifacts()
    artifact_paths = sorted(path for path in support_raw_root().rglob("*") if path.is_file())
    return artifact_paths + [metadata_path(), ground_truth_path()]


def manifest_preview(limit: int = 12) -> list[dict[str, Any]]:
    return [item.model_dump() for item in load_document_manifest()[:limit]]


def ground_truth_summary() -> dict[str, Any]:
    ground_truth = load_ground_truth()
    return {
        "knowledge_document_count": ground_truth["knowledge_document_count"],
        "evaluation_question_count": ground_truth["evaluation_question_count"],
        "chunk_count": ground_truth["chunk_count"],
        "expected_source_ids": sorted(
            {
                source_id
                for item in ground_truth["evaluation_cases"]
                for source_id in item["expected_source_ids"]
            }
        ),
    }
