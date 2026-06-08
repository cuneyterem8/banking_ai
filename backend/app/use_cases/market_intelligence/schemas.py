from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MarketMode = Literal["daily_brief", "research"]
MarketDepth = Literal["quick", "standard", "deep"]
SignalDirection = Literal["positive", "negative", "mixed", "watch"]


class MarketResearchRequest(BaseModel):
    objective: str = "Create a concise banking market intelligence brief for US banking leaders."
    region: str = "US"
    focus_areas: list[str] = Field(default_factory=lambda: ["rates", "deposits", "credit", "regulation"])
    depth: MarketDepth = "standard"
    max_search_calls: int = Field(default=10, ge=0, le=24)
    use_live_web: bool = True


class MarketQueryPlan(BaseModel):
    query_id: str
    question: str
    focus_area: str
    priority: int


class MarketSource(BaseModel):
    source_id: str
    title: str
    url: str
    domain: str
    source_type: str
    query_id: str | None = None
    query: str | None = None
    snippet: str
    retrieved_at: str
    published_at: str | None = None
    verification_status: str = "pending"
    citation_count: int = 0


class MarketEvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    topic: str
    impact_area: str
    claim: str
    sentiment: str
    urgency: str
    confidence: float = Field(ge=0, le=1)
    source_url: str | None = None


class MarketSignal(BaseModel):
    signal_id: str
    topic: str
    sector: str
    impact_area: str
    direction: SignalDirection
    urgency: str
    confidence: float = Field(ge=0, le=1)
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_count: int = 0


class MarketBrief(BaseModel):
    brief_id: str
    headline: str
    executive_summary: str
    top_developments: list[str] = Field(default_factory=list)
    banking_implications: list[str] = Field(default_factory=list)
    risks_and_opportunities: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    watchlist_items: list[str] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class MarketAgentStep(BaseModel):
    step_id: str
    agent_name: str
    status: str
    summary: str
    input_count: int = 0
    output_count: int = 0
    duration_ms: int = 0


class MarketCostControl(BaseModel):
    model_name: str
    fallback_model_name: str
    search_context_size: str
    max_search_calls: int
    search_call_count: int
    estimated_search_cost_usd: float
    live_search_enabled: bool


class MarketIntelligenceSummary(BaseModel):
    mode: MarketMode
    source_count: int
    live_source_count: int
    synthetic_source_count: int
    evidence_count: int
    signal_count: int
    brief_count: int
    search_call_count: int
    estimated_search_cost_usd: float
    warning_count: int
    average_confidence: float
    provider_used: str
    model_name: str


class MarketIntelligencePayload(BaseModel):
    mode: MarketMode
    summary: MarketIntelligenceSummary
    briefs: list[MarketBrief]
    signals: list[MarketSignal]
    sources: list[MarketSource]
    evidence_items: list[MarketEvidenceItem]
    query_plan: list[MarketQueryPlan]
    agent_trace: list[MarketAgentStep]
    cost_control: MarketCostControl
    warnings: list[str] = Field(default_factory=list)


class SearchServiceResult(BaseModel):
    sources: list[MarketSource] = Field(default_factory=list)
    evidence_items: list[MarketEvidenceItem] = Field(default_factory=list)
    agent_steps: list[MarketAgentStep] = Field(default_factory=list)
    provider_used: str
    model_name: str
    search_call_count: int = 0
    estimated_search_cost_usd: float = 0
    warnings: list[str] = Field(default_factory=list)


class SyntheticMarketArticle(BaseModel):
    article_id: str
    title: str
    publisher: str
    published_at: str
    topic: str
    sector: str
    impact_area: str
    sentiment: str
    urgency: str
    summary: str
    url: str


class SyntheticRateRecord(BaseModel):
    date: str
    fed_funds_rate: float
    treasury_10y: float
    mortgage_30y: float
    deposit_beta_index: float
    usd_index: float
    inflation_expectation: float


class SyntheticCompetitorRate(BaseModel):
    competitor_id: str
    competitor_name: str
    product_line: str
    product_name: str
    rate: float
    fee: float
    region: str
    effective_date: str
    source_note: str


class SyntheticCalendarEvent(BaseModel):
    event_id: str
    event_date: str
    event_type: str
    title: str
    expected_impact: str
    affected_areas: list[str] = Field(default_factory=list)
