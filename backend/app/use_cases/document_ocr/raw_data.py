import json
from pathlib import Path
from typing import Any

from app.use_cases.document_ocr.data_generation import (
    document_data_root,
    document_raw_root,
    ground_truth_path,
    metadata_path,
    write_artifacts,
)
from app.use_cases.document_ocr.schemas import DocumentArtifactManifest

USE_CASE_SLUG = "document-ocr"
DATASET_KEY_MANIFEST = "manifest"


def ensure_raw_artifacts() -> None:
    required = [metadata_path(), ground_truth_path()]
    if not all(path.exists() for path in required):
        write_artifacts()
        return
    manifest = load_manifest(regenerate_if_missing=False)
    if not manifest.get("documents"):
        write_artifacts()
        return
    for item in manifest["documents"]:
        if not (document_data_root() / item["relative_path"]).exists():
            write_artifacts()
            return


def load_manifest(*, regenerate_if_missing: bool = True) -> dict[str, Any]:
    if regenerate_if_missing and not metadata_path().exists():
        write_artifacts()
    return json.loads(metadata_path().read_text(encoding="utf-8"))


def load_ground_truth() -> dict[str, Any]:
    ensure_raw_artifacts()
    return json.loads(ground_truth_path().read_text(encoding="utf-8"))


def load_document_manifest() -> list[DocumentArtifactManifest]:
    ensure_raw_artifacts()
    manifest = load_manifest()
    return [DocumentArtifactManifest(**item) for item in manifest["documents"]]


def raw_artifact_paths() -> list[Path]:
    ensure_raw_artifacts()
    artifact_paths = sorted(path for path in document_raw_root().rglob("*") if path.is_file())
    return artifact_paths + [metadata_path(), ground_truth_path()]


def manifest_preview(limit: int = 12) -> list[dict[str, Any]]:
    return [item.model_dump() for item in load_document_manifest()[:limit]]


def ground_truth_summary() -> dict[str, Any]:
    ground_truth = load_ground_truth()
    return {
        "customer_count": ground_truth["customer_count"],
        "document_count": ground_truth["document_count"],
        "expected_field_count": sum(len(item["expected_fields"]) for item in ground_truth["documents"]),
        "expected_table_row_count": sum(
            len(table["rows"]) for item in ground_truth["documents"] for table in item["expected_tables"]
        ),
    }
