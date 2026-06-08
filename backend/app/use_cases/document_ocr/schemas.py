from typing import Any

from pydantic import BaseModel, Field


class DocumentArtifactManifest(BaseModel):
    document_id: str
    customer_id: str
    customer_name: str
    document_type: str
    file_name: str
    relative_path: str
    media_type: str
    is_scanned: bool
    expected_field_count: int
    expected_table_row_count: int = 0


class OcrTable(BaseModel):
    name: str
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DocumentExtraction(BaseModel):
    document_id: str
    customer_id: str
    document_type: str
    file_name: str
    provider_used: str
    extraction_status: str
    confidence: float = Field(ge=0, le=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    tables: list[OcrTable] = Field(default_factory=list)
    validation_issues: list[str] = Field(default_factory=list)
    raw_text_excerpt: str = ""


class DocumentOcrSummary(BaseModel):
    document_count: int
    customer_count: int
    extracted_field_count: int
    expected_field_count: int
    field_accuracy: float
    table_row_recall: float
    average_confidence: float
    fallback_count: int
    timeout_count: int
    warning_count: int
    provider_used: str


class DocumentOcrPayload(BaseModel):
    summary: DocumentOcrSummary
    documents: list[DocumentExtraction]
