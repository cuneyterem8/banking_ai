from sqlmodel import Session, select

from app.db.models import RawArtifact, RawDataset, UseCase
from app.use_cases.aml_monitoring.raw_data import (
    DATASET_KEY_TEST as AML_DATASET_KEY_TEST,
    DATASET_KEY_TRAIN as AML_DATASET_KEY_TRAIN,
    DATASET_KEY_VAL as AML_DATASET_KEY_VAL,
    USE_CASE_SLUG as AML_USE_CASE_SLUG,
    aml_data_relative,
    ground_truth_summary as aml_ground_truth_summary,
    load_test_alerts,
    load_train_alerts,
    load_val_alerts,
    manifest_preview as aml_manifest_preview,
    network_summary as aml_network_summary,
    raw_artifact_paths as aml_raw_artifact_paths,
)
from app.use_cases.credit_risk.raw_data import (
    DATASET_KEY_TEST as CREDIT_DATASET_KEY_TEST,
    DATASET_KEY_TRAIN as CREDIT_DATASET_KEY_TRAIN,
    DATASET_KEY_VAL as CREDIT_DATASET_KEY_VAL,
    USE_CASE_SLUG as CREDIT_USE_CASE_SLUG,
    load_test_applications,
    load_train_applications,
    load_val_applications,
    raw_artifact_paths as credit_raw_artifact_paths,
)
from app.use_cases.document_ocr.raw_data import (
    DATASET_KEY_MANIFEST as DOCUMENT_DATASET_KEY_MANIFEST,
    USE_CASE_SLUG as DOCUMENT_USE_CASE_SLUG,
    document_data_root,
    ground_truth_summary as document_ground_truth_summary,
    load_document_manifest,
    load_manifest as load_document_ocr_manifest,
    manifest_preview as document_manifest_preview,
    raw_artifact_paths as document_raw_artifact_paths,
)
from app.use_cases.email_automation.raw_data import (
    DATASET_KEY_EMAIL_INPUTS as EMAIL_DATASET_KEY_EMAIL_INPUTS,
    USE_CASE_SLUG as EMAIL_USE_CASE_SLUG,
    email_data_relative,
    ground_truth_summary as email_ground_truth_summary,
    load_campaigns as load_email_campaigns,
    load_customers as load_email_customers,
    load_evaluation_cases as load_email_evaluation_cases,
    load_events as load_email_events,
    load_templates as load_email_templates,
    manifest_preview as email_manifest_preview,
    raw_artifact_paths as email_raw_artifact_paths,
)
from app.use_cases.fraud_detection.raw_data import (
    DATASET_KEY_TEST,
    DATASET_KEY_TRAIN,
    DATASET_KEY_VAL,
    USE_CASE_SLUG,
    load_test_transactions,
    load_train_transactions,
    load_val_transactions,
    raw_artifact_paths,
)
from app.use_cases.kyc_kyb.raw_data import (
    DATASET_KEY_BUSINESS_PACKAGES as KYC_KYB_DATASET_KEY_BUSINESS_PACKAGES,
    DATASET_KEY_INDIVIDUAL_PACKAGES as KYC_KYB_DATASET_KEY_INDIVIDUAL_PACKAGES,
    USE_CASE_SLUG as KYC_KYB_USE_CASE_SLUG,
    ground_truth_summary as kyc_kyb_ground_truth_summary,
    kyc_kyb_data_relative,
    load_packages as load_kyc_kyb_packages,
    manifest_preview as kyc_kyb_manifest_preview,
    raw_artifact_paths as kyc_kyb_raw_artifact_paths,
)
from app.use_cases.liquidity_forecast.raw_data import (
    DATASET_KEY_CASH_TIMESERIES as LIQUIDITY_DATASET_KEY_CASH_TIMESERIES,
    USE_CASE_SLUG as LIQUIDITY_USE_CASE_SLUG,
    ground_truth_summary as liquidity_ground_truth_summary,
    liquidity_data_root,
    load_calendar_events as load_liquidity_calendar_events,
    load_history_records as load_liquidity_history_records,
    load_holdout_records as load_liquidity_holdout_records,
    load_manifest as load_liquidity_manifest,
    location_preview as liquidity_location_preview,
    manifest_preview as liquidity_manifest_preview,
    raw_artifact_paths as liquidity_raw_artifact_paths,
)
from app.use_cases.registry import USE_CASES
from app.use_cases.support_chatbot.raw_data import (
    DATASET_KEY_KNOWLEDGE_BASE as SUPPORT_DATASET_KEY_KNOWLEDGE_BASE,
    USE_CASE_SLUG as SUPPORT_USE_CASE_SLUG,
    ground_truth_summary as support_ground_truth_summary,
    load_document_manifest as load_support_manifest_records,
    load_manifest as load_support_manifest,
    manifest_preview as support_manifest_preview,
    raw_artifact_paths as support_raw_artifact_paths,
)
from app.use_cases.support_chatbot.data_generation import support_data_root


PREVIEW_ROW_LIMIT = 30


def _dataset_payload(records: list[dict], *, label_column: str, full_preview: bool = False) -> dict:
    preview = records[:PREVIEW_ROW_LIMIT] if full_preview else []
    return {
        "records": records,
        "preview": preview,
        "record_count": len(records),
        "label_count": sum(int(item.get(label_column, 0)) for item in records),
    }


def _upsert_raw_dataset(
    session: Session,
    *,
    dataset_key: str,
    records: list[dict],
    full_preview: bool,
) -> None:
    payload = _dataset_payload(records, label_column="label_is_fraud", full_preview=full_preview)

    existing = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == USE_CASE_SLUG,
            RawDataset.dataset_key == dataset_key,
        )
    ).first()
    if existing:
        existing.payload = payload
        existing.source_type = "data_directory_files"
        session.add(existing)
    else:
        session.add(
            RawDataset(
                use_case_slug=USE_CASE_SLUG,
                dataset_key=dataset_key,
                source_type="data_directory_files",
                payload=payload,
            )
        )


def seed_use_cases(session: Session) -> None:
    for item in USE_CASES:
        current = session.get(UseCase, item.slug)
        values = {
            "title": item.title,
            "category": item.category,
            "description": item.description,
            "adapter_type": item.adapter_type,
            "model_family": item.model_family,
            "status": item.status,
            "implementation_order": item.implementation_order,
        }
        if current:
            for key, value in values.items():
                setattr(current, key, value)
            session.add(current)
        else:
            session.add(UseCase(slug=item.slug, **values))
    session.commit()


def seed_fraud_detection(session: Session) -> None:
    train_records = [item.model_dump() for item in load_train_transactions()]
    val_records = [item.model_dump() for item in load_val_transactions()]
    test_records = [item.model_dump() for item in load_test_transactions()]

    _upsert_raw_dataset(session, dataset_key=DATASET_KEY_TRAIN, records=train_records, full_preview=False)
    _upsert_raw_dataset(session, dataset_key=DATASET_KEY_VAL, records=val_records, full_preview=True)
    _upsert_raw_dataset(session, dataset_key=DATASET_KEY_TEST, records=test_records, full_preview=True)

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    for path in raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        split = resolved.parent.name
        media_type = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")
        session.add(
            RawArtifact(
                use_case_slug=USE_CASE_SLUG,
                dataset_key=split if split in {DATASET_KEY_TRAIN, DATASET_KEY_VAL, DATASET_KEY_TEST} else "metadata",
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json={"generated": True, "stage": 1, "split": split},
            )
        )
    session.commit()


def seed_credit_risk(session: Session) -> None:
    train_records = [item.model_dump() for item in load_train_applications()]
    val_records = [item.model_dump() for item in load_val_applications()]
    test_records = [item.model_dump() for item in load_test_applications()]

    # _upsert_raw_dataset is fraud-specific for slug; inline the credit version to keep payload shape identical.
    for dataset_key, records, full_preview in (
        (CREDIT_DATASET_KEY_TRAIN, train_records, False),
        (CREDIT_DATASET_KEY_VAL, val_records, True),
        (CREDIT_DATASET_KEY_TEST, test_records, True),
    ):
        payload = _dataset_payload(records, label_column="label_default_12m", full_preview=full_preview)
        existing = session.exec(
            select(RawDataset).where(
                RawDataset.use_case_slug == CREDIT_USE_CASE_SLUG,
                RawDataset.dataset_key == dataset_key,
            )
        ).first()
        if existing:
            existing.payload = payload
            existing.source_type = "data_directory_files"
            session.add(existing)
        else:
            session.add(
                RawDataset(
                    use_case_slug=CREDIT_USE_CASE_SLUG,
                    dataset_key=dataset_key,
                    source_type="data_directory_files",
                    payload=payload,
                )
            )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == CREDIT_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    for path in credit_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        split = resolved.parent.name
        media_type = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")
        session.add(
            RawArtifact(
                use_case_slug=CREDIT_USE_CASE_SLUG,
                dataset_key=split if split in {CREDIT_DATASET_KEY_TRAIN, CREDIT_DATASET_KEY_VAL, CREDIT_DATASET_KEY_TEST} else "metadata",
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json={"generated": True, "stage": 2, "split": split},
            )
        )
    session.commit()


def seed_document_ocr(session: Session) -> None:
    manifest = load_document_ocr_manifest()
    preview = document_manifest_preview()
    payload = {
        "records": manifest["documents"],
        "preview": preview,
        "record_count": manifest["document_count"],
        "document_count": manifest["document_count"],
        "customer_count": manifest["customer_count"],
        "ground_truth_summary": document_ground_truth_summary(),
    }
    existing = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == DOCUMENT_USE_CASE_SLUG,
            RawDataset.dataset_key == DOCUMENT_DATASET_KEY_MANIFEST,
        )
    ).first()
    if existing:
        existing.payload = payload
        existing.source_type = "data_directory_files"
        session.add(existing)
    else:
        session.add(
            RawDataset(
                use_case_slug=DOCUMENT_USE_CASE_SLUG,
                dataset_key=DOCUMENT_DATASET_KEY_MANIFEST,
                source_type="data_directory_files",
                payload=payload,
            )
        )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == DOCUMENT_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    manifest_by_name = {item.relative_path.replace("\\", "/"): item for item in load_document_manifest()}
    for path in document_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        data_relative = str(resolved.relative_to(document_data_root())).replace("\\", "/")
        split = resolved.parent.name
        manifest_item = None
        for item in manifest_by_name.values():
            if item.file_name == resolved.name and item.relative_path.replace("\\", "/").endswith(f"{split}/{resolved.name}"):
                manifest_item = item
                break
        media_type = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")
        dataset_key = manifest_item.customer_id if manifest_item else ("metadata" if resolved.name == "metadata.json" else "ground_truth")
        metadata = {
            "generated": True,
            "stage": 3,
            "relative_path": data_relative if data_relative else relative,
        }
        if manifest_item:
            metadata.update(
                {
                    "document_id": manifest_item.document_id,
                    "document_type": manifest_item.document_type,
                    "is_scanned": manifest_item.is_scanned,
                    "customer_id": manifest_item.customer_id,
                }
            )
        session.add(
            RawArtifact(
                use_case_slug=DOCUMENT_USE_CASE_SLUG,
                dataset_key=dataset_key,
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json=metadata,
            )
        )
    session.commit()


def seed_support_chatbot(session: Session) -> None:
    manifest = load_support_manifest()
    preview = support_manifest_preview()
    payload = {
        "records": manifest["documents"],
        "preview": preview,
        "record_count": manifest["knowledge_document_count"],
        "knowledge_document_count": manifest["knowledge_document_count"],
        "chunk_count": manifest["chunk_count"],
        "evaluation_question_count": manifest["evaluation_question_count"],
        "ground_truth_summary": support_ground_truth_summary(),
    }
    existing = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == SUPPORT_USE_CASE_SLUG,
            RawDataset.dataset_key == SUPPORT_DATASET_KEY_KNOWLEDGE_BASE,
        )
    ).first()
    if existing:
        existing.payload = payload
        existing.source_type = "data_directory_files"
        session.add(existing)
    else:
        session.add(
            RawDataset(
                use_case_slug=SUPPORT_USE_CASE_SLUG,
                dataset_key=SUPPORT_DATASET_KEY_KNOWLEDGE_BASE,
                source_type="data_directory_files",
                payload=payload,
            )
        )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == SUPPORT_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    manifest_by_path = {item.relative_path.replace("\\", "/"): item for item in load_support_manifest_records()}
    for path in support_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        data_relative = str(resolved.relative_to(support_data_root())).replace("\\", "/")
        manifest_item = manifest_by_path.get(data_relative)
        if manifest_item:
            dataset_key = manifest_item.source_type
        elif resolved.name == "support_questions.json":
            dataset_key = "evaluation"
        elif resolved.name == "metadata.json":
            dataset_key = "metadata"
        else:
            dataset_key = "ground_truth"
        media_type = {
            ".pdf": "application/pdf",
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")
        metadata = {
            "generated": True,
            "stage": 4,
            "relative_path": data_relative,
        }
        if manifest_item:
            metadata.update(
                {
                    "source_id": manifest_item.source_id,
                    "source_type": manifest_item.source_type,
                    "topic": manifest_item.topic,
                    "title": manifest_item.title,
                }
            )
        session.add(
            RawArtifact(
                use_case_slug=SUPPORT_USE_CASE_SLUG,
                dataset_key=dataset_key,
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json=metadata,
            )
        )
    session.commit()


def seed_liquidity_forecast(session: Session) -> None:
    manifest = load_liquidity_manifest()
    history_records = [item.model_dump() for item in load_liquidity_history_records()]
    holdout_records = [item.model_dump() for item in load_liquidity_holdout_records()]
    calendar_events = [item.model_dump() for item in load_liquidity_calendar_events()]
    payload = {
        "records": history_records,
        "preview": liquidity_manifest_preview(),
        "record_count": len(history_records),
        "history_record_count": len(history_records),
        "holdout_record_count": len(holdout_records),
        "location_count": manifest["location_count"],
        "forecast_horizon_days": manifest["forecast_horizon_days"],
        "history_days": manifest["history_days"],
        "location_preview": liquidity_location_preview(),
        "calendar_event_count": len(calendar_events),
        "calendar_preview": calendar_events,
        "ground_truth_summary": liquidity_ground_truth_summary(),
    }
    existing = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == LIQUIDITY_USE_CASE_SLUG,
            RawDataset.dataset_key == LIQUIDITY_DATASET_KEY_CASH_TIMESERIES,
        )
    ).first()
    if existing:
        existing.payload = payload
        existing.source_type = "data_directory_files"
        session.add(existing)
    else:
        session.add(
            RawDataset(
                use_case_slug=LIQUIDITY_USE_CASE_SLUG,
                dataset_key=LIQUIDITY_DATASET_KEY_CASH_TIMESERIES,
                source_type="data_directory_files",
                payload=payload,
            )
        )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == LIQUIDITY_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    for path in liquidity_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        data_relative = str(resolved.relative_to(liquidity_data_root())).replace("\\", "/")
        if data_relative.startswith("raw/timeseries"):
            dataset_key = "timeseries"
        elif data_relative.startswith("raw/calendar"):
            dataset_key = "calendar"
        elif data_relative.startswith("raw/policies"):
            dataset_key = "policies"
        elif resolved.name == "metadata.json":
            dataset_key = "metadata"
        else:
            dataset_key = "ground_truth"
        media_type = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".csv": "text/csv",
            ".pdf": "application/pdf",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")
        session.add(
            RawArtifact(
                use_case_slug=LIQUIDITY_USE_CASE_SLUG,
                dataset_key=dataset_key,
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json={
                    "generated": True,
                    "stage": 5,
                    "relative_path": data_relative,
                },
            )
        )
    session.commit()


def seed_aml_monitoring(session: Session) -> None:
    train_records = [item.model_dump() for item in load_train_alerts()]
    val_records = [item.model_dump() for item in load_val_alerts()]
    test_records = [item.model_dump() for item in load_test_alerts()]
    ground_truth = aml_ground_truth_summary()
    network = aml_network_summary().model_dump()

    for dataset_key, records, full_preview in (
        (AML_DATASET_KEY_TRAIN, train_records, False),
        (AML_DATASET_KEY_VAL, val_records, True),
        (AML_DATASET_KEY_TEST, test_records, True),
    ):
        payload = _dataset_payload(records, label_column="label_sar_recommended", full_preview=full_preview)
        payload.update(
            {
                "manifest_preview": aml_manifest_preview(),
                "ground_truth_summary": ground_truth,
                "network_summary": network,
            }
        )
        existing = session.exec(
            select(RawDataset).where(
                RawDataset.use_case_slug == AML_USE_CASE_SLUG,
                RawDataset.dataset_key == dataset_key,
            )
        ).first()
        if existing:
            existing.payload = payload
            existing.source_type = "data_directory_files"
            session.add(existing)
        else:
            session.add(
                RawDataset(
                    use_case_slug=AML_USE_CASE_SLUG,
                    dataset_key=dataset_key,
                    source_type="data_directory_files",
                    payload=payload,
                )
            )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == AML_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    for path in aml_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        data_relative = aml_data_relative(resolved)
        if data_relative.startswith("raw/train"):
            dataset_key = "train"
        elif data_relative.startswith("raw/val"):
            dataset_key = "val"
        elif data_relative.startswith("raw/test"):
            dataset_key = "test"
        elif data_relative.startswith("raw/network"):
            dataset_key = "network"
        elif data_relative.startswith("raw/entities"):
            dataset_key = "entities"
        elif data_relative.startswith("raw/cases"):
            dataset_key = "case_notes"
        elif resolved.name == "metadata.json":
            dataset_key = "metadata"
        else:
            dataset_key = "ground_truth"
        media_type = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".json": "application/json",
            ".pdf": "application/pdf",
        }.get(extension, "application/octet-stream")
        session.add(
            RawArtifact(
                use_case_slug=AML_USE_CASE_SLUG,
                dataset_key=dataset_key,
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json={
                    "generated": True,
                    "stage": 6,
                    "relative_path": data_relative,
                },
            )
        )
    session.commit()


def seed_kyc_kyb(session: Session) -> None:
    individual_records = [item.model_dump() for item in load_kyc_kyb_packages(subject_type="individual")]
    business_records = [item.model_dump() for item in load_kyc_kyb_packages(subject_type="business")]
    ground_truth = kyc_kyb_ground_truth_summary()

    for dataset_key, subject_type, records in (
        (KYC_KYB_DATASET_KEY_INDIVIDUAL_PACKAGES, "individual", individual_records),
        (KYC_KYB_DATASET_KEY_BUSINESS_PACKAGES, "business", business_records),
    ):
        payload = {
            "records": records,
            "preview": kyc_kyb_manifest_preview(subject_type=subject_type),
            "record_count": len(records),
            "package_count": len(records),
            "document_count": sum(len(item.get("documents", [])) for item in records),
            "manual_review_label_count": sum(int(item.get("label_manual_review_required", 0)) for item in records),
            "ground_truth_summary": ground_truth,
        }
        existing = session.exec(
            select(RawDataset).where(
                RawDataset.use_case_slug == KYC_KYB_USE_CASE_SLUG,
                RawDataset.dataset_key == dataset_key,
            )
        ).first()
        if existing:
            existing.payload = payload
            existing.source_type = "data_directory_files"
            session.add(existing)
        else:
            session.add(
                RawDataset(
                    use_case_slug=KYC_KYB_USE_CASE_SLUG,
                    dataset_key=dataset_key,
                    source_type="data_directory_files",
                    payload=payload,
                )
            )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == KYC_KYB_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    for path in kyc_kyb_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        data_relative = kyc_kyb_data_relative(resolved)
        if data_relative.startswith("raw/individuals"):
            dataset_key = KYC_KYB_DATASET_KEY_INDIVIDUAL_PACKAGES
        elif data_relative.startswith("raw/businesses"):
            dataset_key = KYC_KYB_DATASET_KEY_BUSINESS_PACKAGES
        elif data_relative.startswith("raw/reference"):
            dataset_key = "reference"
        elif resolved.name == "metadata.json":
            dataset_key = "metadata"
        else:
            dataset_key = "ground_truth"
        media_type = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")
        session.add(
            RawArtifact(
                use_case_slug=KYC_KYB_USE_CASE_SLUG,
                dataset_key=dataset_key,
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json={
                    "generated": True,
                    "stage": 7,
                    "relative_path": data_relative,
                },
            )
        )
    session.commit()


def seed_email_automation(session: Session) -> None:
    customers = [item.model_dump() for item in load_email_customers()]
    events = [item.model_dump() for item in load_email_events()]
    campaigns = [item.model_dump() for item in load_email_campaigns()]
    templates = [item.model_dump() for item in load_email_templates()]
    cases = [item.model_dump() for item in load_email_evaluation_cases()]
    ground_truth = email_ground_truth_summary()
    payload = {
        "records": cases,
        "customers": customers,
        "events": events,
        "campaigns": campaigns,
        "templates": templates,
        "preview": email_manifest_preview(),
        "record_count": len(customers) + len(events) + len(campaigns) + len(cases),
        "customer_count": len(customers),
        "service_event_count": len(events),
        "campaign_audience_count": len(campaigns),
        "template_count": len(templates),
        "evaluation_case_count": len(cases),
        "ground_truth_summary": ground_truth,
    }
    existing = session.exec(
        select(RawDataset).where(
            RawDataset.use_case_slug == EMAIL_USE_CASE_SLUG,
            RawDataset.dataset_key == EMAIL_DATASET_KEY_EMAIL_INPUTS,
        )
    ).first()
    if existing:
        existing.payload = payload
        existing.source_type = "data_directory_files"
        session.add(existing)
    else:
        session.add(
            RawDataset(
                use_case_slug=EMAIL_USE_CASE_SLUG,
                dataset_key=EMAIL_DATASET_KEY_EMAIL_INPUTS,
                source_type="data_directory_files",
                payload=payload,
            )
        )

    existing_artifacts = session.exec(select(RawArtifact).where(RawArtifact.use_case_slug == EMAIL_USE_CASE_SLUG)).all()
    for artifact in existing_artifacts:
        session.delete(artifact)

    for path in email_raw_artifact_paths():
        resolved = path.resolve()
        extension = resolved.suffix.lower()
        data_relative = email_data_relative(resolved)
        if data_relative.startswith("raw/events"):
            dataset_key = "events"
        elif data_relative.startswith("raw/customers"):
            dataset_key = "customers"
        elif data_relative.startswith("raw/campaigns"):
            dataset_key = "campaigns"
        elif data_relative.startswith("raw/templates"):
            dataset_key = "templates"
        elif data_relative.startswith("raw/policies"):
            dataset_key = "policies"
        elif data_relative.startswith("raw/evaluation"):
            dataset_key = "evaluation"
        elif resolved.name == "metadata.json":
            dataset_key = "metadata"
        else:
            dataset_key = "ground_truth"
        media_type = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".json": "application/json",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
        }.get(extension, "application/octet-stream")
        session.add(
            RawArtifact(
                use_case_slug=EMAIL_USE_CASE_SLUG,
                dataset_key=dataset_key,
                file_name=resolved.name,
                file_path=str(resolved),
                artifact_type=extension.removeprefix(".") or "json",
                media_type=media_type,
                metadata_json={
                    "generated": True,
                    "stage": 8,
                    "relative_path": data_relative,
                },
            )
        )
    session.commit()


def seed_all(session: Session) -> None:
    seed_use_cases(session)
    seed_fraud_detection(session)
    seed_credit_risk(session)
    seed_document_ocr(session)
    seed_support_chatbot(session)
    seed_liquidity_forecast(session)
    seed_aml_monitoring(session)
    seed_kyc_kyb(session)
    seed_email_automation(session)
