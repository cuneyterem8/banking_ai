from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.utcnow()


json_column = JSON().with_variant(JSONB, "postgresql")


class UseCase(SQLModel, table=True):
    __tablename__ = "use_cases"

    slug: str = Field(primary_key=True)
    title: str
    category: str
    description: str
    adapter_type: str
    model_family: str
    status: str = Field(index=True)
    implementation_order: int = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))


class RawDataset(SQLModel, table=True):
    __tablename__ = "raw_datasets"

    id: str = Field(default_factory=new_id, primary_key=True)
    use_case_slug: str = Field(index=True, foreign_key="use_cases.slug")
    dataset_key: str = Field(index=True)
    source_type: str
    payload: dict = Field(default_factory=dict, sa_column=Column(json_column, nullable=False))
    seeded_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))


class RawArtifact(SQLModel, table=True):
    __tablename__ = "raw_artifacts"

    id: str = Field(default_factory=new_id, primary_key=True)
    use_case_slug: str = Field(index=True, foreign_key="use_cases.slug")
    dataset_key: str = Field(index=True)
    file_name: str
    file_path: str
    artifact_type: str
    media_type: str
    metadata_json: dict = Field(default_factory=dict, sa_column=Column("metadata", json_column, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))


class ModelRun(SQLModel, table=True):
    __tablename__ = "model_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    use_case_slug: str = Field(index=True, foreign_key="use_cases.slug")
    adapter_type: str
    provider_used: str
    model_name: str
    status: str = Field(index=True)
    duration_ms: int | None = None
    metrics: dict = Field(default_factory=dict, sa_column=Column(json_column, nullable=False))
    error_message: str | None = None
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))


class ProcessedResult(SQLModel, table=True):
    __tablename__ = "processed_results"

    id: str = Field(default_factory=new_id, primary_key=True)
    run_id: str = Field(index=True, foreign_key="model_runs.id")
    use_case_slug: str = Field(index=True, foreign_key="use_cases.slug")
    result_type: str
    payload: dict = Field(default_factory=dict, sa_column=Column(json_column, nullable=False))
    explanation: dict = Field(default_factory=dict, sa_column=Column(json_column, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))


class ModelArtifact(SQLModel, table=True):
    __tablename__ = "model_artifacts"

    id: str = Field(default_factory=new_id, primary_key=True)
    use_case_slug: str = Field(index=True, foreign_key="use_cases.slug")
    artifact_type: str
    local_path: str
    metadata_json: dict = Field(default_factory=dict, sa_column=Column("metadata", json_column, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: str = Field(default_factory=new_id, primary_key=True)
    actor: str
    action: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_id: str
    metadata_json: dict = Field(default_factory=dict, sa_column=Column("metadata", json_column, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime, nullable=False))
