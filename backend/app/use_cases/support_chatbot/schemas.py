from typing import Any

from pydantic import BaseModel, Field


class SupportDocumentManifest(BaseModel):
    source_id: str
    source_file: str
    source_type: str
    topic: str
    title: str
    relative_path: str
    media_type: str
    checksum: str


class SupportKnowledgeChunk(BaseModel):
    chunk_id: str
    source_id: str
    source_file: str
    source_type: str
    topic: str
    title: str
    text: str
    char_start: int
    char_end: int
    checksum: str


class RetrievedSource(BaseModel):
    source_id: str
    source_file: str
    chunk_id: str
    title: str
    quote: str
    score: float = 0


class SupportChatbotAnswer(BaseModel):
    question_id: str | None = None
    question: str
    answer: str
    answer_status: str
    provider_used: str
    model_name: str
    confidence: float = Field(ge=0, le=1)
    retrieval_confidence: float = Field(ge=0, le=1)
    sources: list[RetrievedSource] = Field(default_factory=list)
    escalation_required: bool = False
    escalation_reason: str | None = None
    policy_tags: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SupportEvaluationCase(BaseModel):
    question_id: str
    question: str
    expected_source_ids: list[str]
    must_cite: list[str]
    expected_tags: list[str]
    escalation_expected: bool = False


class SupportChatbotSummary(BaseModel):
    question_count: int
    answered_count: int
    citation_accuracy: float
    source_recall: float
    average_confidence: float
    fallback_count: int
    timeout_count: int
    invalid_json_count: int
    escalation_count: int
    warning_count: int
    provider_used: str


class SupportChatbotPayload(BaseModel):
    summary: SupportChatbotSummary
    answers: list[SupportChatbotAnswer]
    retrieved_chunks: list[SupportKnowledgeChunk] = Field(default_factory=list)


class SupportChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=800)


class SupportChatResponse(BaseModel):
    run: dict[str, Any]
    result: dict[str, Any]
    payload: SupportChatbotPayload
