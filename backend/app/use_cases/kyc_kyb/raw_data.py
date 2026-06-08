from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.use_cases.kyc_kyb.data_generation import (
    BUSINESS_COUNT,
    INDIVIDUAL_COUNT,
    ground_truth_path,
    kyc_kyb_data_root,
    kyc_kyb_raw_root,
    metadata_path,
    write_artifacts,
)
from app.use_cases.kyc_kyb.schemas import KycKybPackageRecord

USE_CASE_SLUG = "kyc-kyb"
DATASET_KEY_INDIVIDUAL_PACKAGES = "individual_packages"
DATASET_KEY_BUSINESS_PACKAGES = "business_packages"


def ensure_raw_artifacts() -> None:
    required = [metadata_path(), ground_truth_path()]
    if not all(path.exists() for path in required):
        write_artifacts()
        return
    manifest = load_manifest(regenerate_if_missing=False)
    if manifest.get("individual_count") != INDIVIDUAL_COUNT or manifest.get("business_count") != BUSINESS_COUNT:
        write_artifacts()
        return
    ground_truth = load_ground_truth(regenerate_if_missing=False)
    for package in ground_truth.get("packages", []):
        for document in package.get("documents", []):
            if not (kyc_kyb_data_root() / document["relative_path"]).exists():
                write_artifacts()
                return


def load_manifest(*, regenerate_if_missing: bool = True) -> dict[str, Any]:
    if regenerate_if_missing and not metadata_path().exists():
        write_artifacts()
    return json.loads(metadata_path().read_text(encoding="utf-8"))


def load_ground_truth(*, regenerate_if_missing: bool = True) -> dict[str, Any]:
    if regenerate_if_missing:
        ensure_raw_artifacts()
    return json.loads(ground_truth_path().read_text(encoding="utf-8"))


def load_packages(split: str | None = None, subject_type: str | None = None) -> list[KycKybPackageRecord]:
    ensure_raw_artifacts()
    packages = [KycKybPackageRecord(**item) for item in load_ground_truth()["packages"]]
    if split is not None:
        packages = [item for item in packages if item.split == split]
    if subject_type is not None:
        packages = [item for item in packages if item.subject_type == subject_type]
    return packages


def load_train_packages() -> list[KycKybPackageRecord]:
    return load_packages(split="train")


def load_val_packages() -> list[KycKybPackageRecord]:
    return load_packages(split="val")


def load_test_packages() -> list[KycKybPackageRecord]:
    return load_packages(split="test")


def raw_artifact_paths() -> list[Path]:
    ensure_raw_artifacts()
    artifact_paths = sorted(path for path in kyc_kyb_raw_root().rglob("*") if path.is_file())
    return artifact_paths + [metadata_path(), ground_truth_path()]


def manifest_preview(subject_type: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
    packages = load_packages(subject_type=subject_type)
    return [
        {
            "package_id": item.package_id,
            "subject_type": item.subject_type,
            "subject_name": item.subject_name,
            "split": item.split,
            "jurisdiction": item.jurisdiction,
            "document_count": len(item.documents),
            "expected_status": item.expected_status,
            "label_manual_review_required": item.label_manual_review_required,
            "expected_rule_flags": ", ".join(item.expected_rule_flags) if item.expected_rule_flags else "none",
        }
        for item in packages[:limit]
    ]


def ground_truth_summary() -> dict[str, Any]:
    ground_truth = load_ground_truth()
    return {
        "individual_count": ground_truth["individual_count"],
        "business_count": ground_truth["business_count"],
        "package_count": ground_truth["package_count"],
        "split_summary": ground_truth["split_summary"],
        "expected_rule_flags": ground_truth["expected_rule_flags"],
    }


def kyc_kyb_data_relative(path: Path) -> str:
    return str(path.resolve().relative_to(kyc_kyb_data_root().resolve())).replace("\\", "/")
