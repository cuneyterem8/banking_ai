from sqlmodel import Session, select

from app.db.models import AuditEvent, ModelArtifact, ModelRun, ProcessedResult, RawArtifact, RawDataset
from app.services.run_cleanup import (
    STARTUP_USE_CASE_SLUGS,
    clear_fraud_test_runs,
    clear_fraud_val_runs,
    reset_fraud_for_training,
    reset_startup_outputs,
)
from app.use_cases.fraud_detection.service import FRAUD_TEST_RESULT_TYPE, FRAUD_VAL_RESULT_TYPE
from app.use_cases.fraud_detection.raw_data import USE_CASE_SLUG


def test_clear_fraud_test_runs_keeps_val_removes_test(session: Session) -> None:
    val_run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="completed",
        metrics={"split": "val", "accuracy": 0.91},
    )
    test_run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="completed",
        metrics={"split": "test", "accuracy": 0.88},
    )
    session.add(val_run)
    session.add(test_run)
    session.commit()
    session.refresh(val_run)
    session.refresh(test_run)

    session.add(
        ProcessedResult(
            run_id=val_run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=FRAUD_VAL_RESULT_TYPE,
            payload={"split": "val"},
            explanation={},
        )
    )
    session.add(
        ProcessedResult(
            run_id=test_run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=FRAUD_TEST_RESULT_TYPE,
            payload={"split": "test"},
            explanation={},
        )
    )
    session.commit()

    removed = clear_fraud_test_runs(session)
    assert removed == 1

    remaining = session.exec(select(ModelRun).where(ModelRun.use_case_slug == USE_CASE_SLUG)).all()
    assert len(remaining) == 1
    assert remaining[0].metrics["split"] == "val"

    results = session.exec(select(ProcessedResult).where(ProcessedResult.use_case_slug == USE_CASE_SLUG)).all()
    assert len(results) == 1
    assert results[0].result_type == FRAUD_VAL_RESULT_TYPE


def test_reset_fraud_for_training_clears_val_and_test(session: Session) -> None:
    val_run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="completed",
        metrics={"split": "val"},
    )
    test_run = ModelRun(
        use_case_slug=USE_CASE_SLUG,
        adapter_type="autogluon-tabular",
        provider_used="local-autogluon",
        model_name="autogluon.tabular.TabularPredictor",
        status="completed",
        metrics={"split": "test"},
    )
    session.add(val_run)
    session.add(test_run)
    session.commit()
    session.refresh(val_run)
    session.refresh(test_run)
    session.add(
        ProcessedResult(
            run_id=val_run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=FRAUD_VAL_RESULT_TYPE,
            payload={},
            explanation={},
        )
    )
    session.add(
        ProcessedResult(
            run_id=test_run.id,
            use_case_slug=USE_CASE_SLUG,
            result_type=FRAUD_TEST_RESULT_TYPE,
            payload={},
            explanation={},
        )
    )
    session.commit()

    reset_fraud_for_training(session)

    runs = session.exec(select(ModelRun).where(ModelRun.use_case_slug == USE_CASE_SLUG)).all()
    results = session.exec(select(ProcessedResult).where(ProcessedResult.use_case_slug == USE_CASE_SLUG)).all()
    assert runs == []
    assert results == []


def test_reset_startup_outputs_clears_model_outputs_but_keeps_raw_records(session: Session) -> None:
    for slug in STARTUP_USE_CASE_SLUGS:
        run = ModelRun(
            use_case_slug=slug,
            adapter_type="startup-test",
            provider_used="local-test",
            model_name="test-model",
            status="completed",
            metrics={"split": "startup"},
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        session.add(
            ProcessedResult(
                run_id=run.id,
                use_case_slug=slug,
                result_type="startup_test_result",
                payload={"slug": slug},
                explanation={},
            )
        )
        session.add(
            ModelArtifact(
                use_case_slug=slug,
                artifact_type="test-artifact",
                local_path=f"storage/models/{slug}/test",
                metadata_json={},
            )
        )
        session.add(
            AuditEvent(
                actor="System",
                action="startup_test_completed",
                entity_type="model_run",
                entity_id=run.id,
                metadata_json={},
            )
        )
        session.add(
            RawDataset(
                use_case_slug=slug,
                dataset_key="raw-test",
                source_type="synthetic",
                payload={"slug": slug},
            )
        )
        session.add(
            RawArtifact(
                use_case_slug=slug,
                dataset_key="raw-test",
                file_name=f"{slug}.csv",
                file_path=f"data/{slug}/raw/{slug}.csv",
                artifact_type="csv",
                media_type="text/csv",
                metadata_json={},
            )
        )
    session.commit()

    reset_startup_outputs(session)

    assert session.exec(select(ModelRun)).all() == []
    assert session.exec(select(ProcessedResult)).all() == []
    assert session.exec(select(ModelArtifact)).all() == []
    assert session.exec(select(AuditEvent).where(AuditEvent.entity_type == "model_run")).all() == []
    assert len(session.exec(select(RawDataset)).all()) == len(STARTUP_USE_CASE_SLUGS)
    assert len(session.exec(select(RawArtifact)).all()) == len(STARTUP_USE_CASE_SLUGS)
