export type UseCase = {
  slug: string;
  title: string;
  category: string;
  description: string;
  adapter_type: string;
  model_family: string;
  status: "implemented" | "planned";
  implementation_order: number;
  latest_run?: ModelRun | null;
  artifact_count?: number;
  result_count?: number;
};

export type RawArtifact = {
  id: string;
  use_case_slug: string;
  dataset_key: string;
  file_name: string;
  file_path: string;
  artifact_type: string;
  media_type: string;
  metadata_json: Record<string, unknown>;
};

export type RawDataset = {
  id: string;
  use_case_slug: string;
  dataset_key: string;
  source_type: string;
  payload: {
    preview?: Record<string, unknown>[];
    records?: Record<string, unknown>[];
    record_count?: number;
    label_count?: number;
    document_count?: number;
    customer_count?: number;
    knowledge_document_count?: number;
    chunk_count?: number;
    evaluation_question_count?: number;
    history_record_count?: number;
    holdout_record_count?: number;
    location_count?: number;
    forecast_horizon_days?: number;
    history_days?: number;
    calendar_event_count?: number;
    location_preview?: Record<string, unknown>[];
    calendar_preview?: Record<string, unknown>[];
    manifest_preview?: Record<string, unknown>[];
    network_summary?: Record<string, unknown>;
    ground_truth_summary?: Record<string, unknown>;
    package_count?: number;
    manual_review_label_count?: number;
    service_event_count?: number;
    campaign_audience_count?: number;
    template_count?: number;
    evaluation_case_count?: number;
    customers?: Record<string, unknown>[];
    events?: Record<string, unknown>[];
    campaigns?: Record<string, unknown>[];
    templates?: Record<string, unknown>[];
    news?: Record<string, unknown>[];
    rates?: Record<string, unknown>[];
    competitors?: Record<string, unknown>[];
    calendar_events?: Record<string, unknown>[];
    taxonomy?: Record<string, unknown>;
    news_count?: number;
    rate_record_count?: number;
    competitor_rate_count?: number;
    topic_count?: number;
  };
};

export type ModelRun = {
  id: string;
  use_case_slug: string;
  adapter_type: string;
  provider_used: string;
  model_name: string;
  status: "running" | "completed" | "failed";
  duration_ms?: number | null;
  metrics: Record<string, unknown>;
  error_message?: string | null;
  started_at: string;
  finished_at?: string | null;
};

export type FraudDecision = {
  transaction_id: string;
  customer_id: string;
  amount: number;
  actual_is_fraud: number;
  predicted_is_fraud: number;
  fraud_probability: number;
  risk_level: "Low" | "Medium" | "High";
  decision: string;
  top_factors: string[];
};

export type CreditDecision = {
  application_id: string;
  customer_id: string;
  requested_loan_amount: number;
  actual_default_12m: number;
  predicted_default_12m: number;
  pd_probability: number;
  risk_grade: "A" | "B" | "C" | "D" | "E";
  decision: string;
  recommended_limit: number;
  expected_loss: number;
  top_factors: string[];
};

export type AmlAlertDecision = {
  alert_id: string;
  customer_id: string;
  account_id: string;
  typology_tag: string;
  sar_probability: number;
  risk_level: "Low" | "Medium" | "High" | "Critical";
  predicted_sar_recommended: number;
  actual_sar_recommended: number;
  decision: string;
  top_factors: string[];
  related_entities: string[];
  linked_transaction_count: number;
  provider_used: string;
};

export type AmlNarrativeDraft = {
  narrative_status: string;
  alert_id: string;
  summary: string;
  suspicious_activity_type: string;
  evidence_bullets: string[];
  recommended_next_steps: string[];
  missing_information: string[];
  confidence: number;
  provider_used: string;
  model_name: string;
  warnings: string[];
};

export type AmlNetworkSummary = {
  account_count: number;
  counterparty_count: number;
  transaction_count: number;
  alert_link_count: number;
  entity_count: number;
  cluster_count: number;
  high_risk_cluster_count: number;
  high_risk_jurisdictions: string[];
  top_clusters: Record<string, unknown>[];
};

export type AmlCaseNoteSummary = {
  file_name: string;
  note_count: number;
  escalation_topic_count: number;
  guidance_excerpt: string;
};

export type AmlMonitoringSummary = {
  split: string;
  alert_count: number;
  sar_label_count: number;
  high_risk_count: number;
  critical_risk_count: number;
  narrative_count: number;
  fallback_count: number;
  timeout_count: number;
  invalid_json_count: number;
  warning_count: number;
  average_sar_probability: number;
  provider_used: string;
  model_name: string;
  primary_score?: number | null;
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
  roc_auc?: number | null;
  threshold: number;
};

export type AmlMonitoringPayload = {
  split: string;
  summary: AmlMonitoringSummary;
  evaluation: SplitEvaluation;
  alerts: AmlAlertDecision[];
  narratives: AmlNarrativeDraft[];
  network_summary: AmlNetworkSummary;
  case_note_summary: AmlCaseNoteSummary;
  warnings: string[];
};

export type KycKybPackageDecision = {
  package_id: string;
  subject_type: "individual" | "business";
  subject_name: string;
  verification_status: "Approved" | "Needs Review" | "Rejected";
  risk_score: number;
  risk_level: "Low" | "Medium" | "High" | "Critical";
  manual_review_required: number;
  actual_manual_review_required: number;
  hard_rule_triggered: boolean;
  top_factors: string[];
  missing_documents: string[];
  field_mismatches: string[];
  provider_used: string;
};

export type KycKybExtractedDocument = {
  package_id: string;
  document_id: string;
  document_type: string;
  file_name: string;
  provider_used: string;
  extraction_status: string;
  confidence: number;
  fields: Record<string, unknown>;
  validation_issues: string[];
  raw_text_excerpt: string;
};

export type KycKybRuleFinding = {
  package_id: string;
  rule_id: string;
  severity: string;
  status: string;
  message: string;
  evidence_fields: Record<string, unknown>;
};

export type KycKybSummary = {
  split: string;
  package_count: number;
  individual_count: number;
  business_count: number;
  manual_review_label_count: number;
  needs_review_count: number;
  rejected_count: number;
  hard_rule_count: number;
  extracted_document_count: number;
  fallback_count: number;
  warning_count: number;
  average_risk_score: number;
  provider_used: string;
  model_name: string;
  primary_score?: number | null;
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
  roc_auc?: number | null;
  threshold: number;
};

export type KycKybPayload = {
  split: string;
  summary: KycKybSummary;
  evaluation: SplitEvaluation;
  packages: Record<string, unknown>[];
  extracted_documents: KycKybExtractedDocument[];
  rule_findings: KycKybRuleFinding[];
  risk_decisions: KycKybPackageDecision[];
  warnings: string[];
};

export type EmailAutomationDraft = {
  draft_id: string;
  case_id: string;
  customer_id: string;
  communication_type: string;
  event_type?: string | null;
  campaign_id?: string | null;
  subject: string;
  preheader: string;
  body: string;
  call_to_action: string;
  provider_used: string;
  model_name: string;
  generation_status: string;
  confidence: number;
  compliance_status: string;
  risk_level: string;
  required_disclosures: string[];
  personalization_used: string[];
  tone_tags: string[];
  validation_issues: string[];
  warnings: string[];
};

export type EmailComplianceFinding = {
  draft_id: string;
  rule_id: string;
  severity: string;
  status: string;
  message: string;
  evidence: Record<string, unknown>;
};

export type EmailAutomationScore = {
  draft_id: string;
  quality_score: number;
  compliance_score: number;
  personalization_score: number;
  readability_score: number;
};

export type EmailAutomationSummary = {
  mode: string;
  draft_count: number;
  service_draft_count: number;
  campaign_draft_count: number;
  approved_count: number;
  needs_review_count: number;
  rejected_count: number;
  fallback_count: number;
  timeout_count: number;
  invalid_json_count: number;
  warning_count: number;
  average_quality_score: number;
  approval_rate: number;
  provider_used: string;
  model_name: string;
};

export type EmailAutomationPayload = {
  mode: string;
  summary: EmailAutomationSummary;
  drafts: EmailAutomationDraft[];
  compliance_findings: EmailComplianceFinding[];
  scores: EmailAutomationScore[];
  warnings: string[];
};

export type EmailDraftRequest = {
  customer_id: string;
  communication_type: "service" | "campaign";
  event_type?: string | null;
  campaign_id?: string | null;
  custom_context?: string;
};

export type EmailDraftResponse = {
  run: ModelRun;
  result: ProcessedResult;
  payload: EmailAutomationPayload;
};

export type MarketSource = {
  source_id: string;
  title: string;
  url: string;
  domain: string;
  source_type: string;
  query_id?: string | null;
  query?: string | null;
  snippet: string;
  retrieved_at: string;
  published_at?: string | null;
  verification_status: string;
  citation_count: number;
};

export type MarketEvidenceItem = {
  evidence_id: string;
  source_id: string;
  topic: string;
  impact_area: string;
  claim: string;
  sentiment: string;
  urgency: string;
  confidence: number;
  source_url?: string | null;
};

export type MarketSignal = {
  signal_id: string;
  topic: string;
  sector: string;
  impact_area: string;
  direction: "positive" | "negative" | "mixed" | "watch";
  urgency: string;
  confidence: number;
  summary: string;
  evidence_ids: string[];
  evidence_count: number;
};

export type MarketBrief = {
  brief_id: string;
  headline: string;
  executive_summary: string;
  top_developments: string[];
  banking_implications: string[];
  risks_and_opportunities: string[];
  recommended_actions: string[];
  watchlist_items: string[];
  cited_source_ids: string[];
  confidence: number;
};

export type MarketAgentStep = {
  step_id: string;
  agent_name: string;
  status: string;
  summary: string;
  input_count: number;
  output_count: number;
  duration_ms: number;
};

export type MarketCostControl = {
  model_name: string;
  fallback_model_name: string;
  search_context_size: string;
  max_search_calls: number;
  search_call_count: number;
  estimated_search_cost_usd: number;
  live_search_enabled: boolean;
};

export type MarketIntelligenceSummary = {
  mode: "daily_brief" | "research";
  source_count: number;
  live_source_count: number;
  synthetic_source_count: number;
  evidence_count: number;
  signal_count: number;
  brief_count: number;
  search_call_count: number;
  estimated_search_cost_usd: number;
  warning_count: number;
  average_confidence: number;
  provider_used: string;
  model_name: string;
};

export type MarketIntelligencePayload = {
  mode: "daily_brief" | "research";
  summary: MarketIntelligenceSummary;
  briefs: MarketBrief[];
  signals: MarketSignal[];
  sources: MarketSource[];
  evidence_items: MarketEvidenceItem[];
  query_plan: Record<string, unknown>[];
  agent_trace: MarketAgentStep[];
  cost_control: MarketCostControl;
  warnings: string[];
};

export type MarketResearchRequest = {
  objective: string;
  region: string;
  focus_areas: string[];
  depth: "quick" | "standard" | "deep";
  max_search_calls: number;
  use_live_web: boolean;
};

export type MarketResearchResponse = {
  run: ModelRun;
  result: ProcessedResult;
  payload: MarketIntelligencePayload;
};

export type DecisionRecord = FraudDecision | CreditDecision | AmlAlertDecision | KycKybPackageDecision;

export type OcrTable = {
  name: string;
  rows: Record<string, unknown>[];
};

export type DocumentExtraction = {
  document_id: string;
  customer_id: string;
  document_type: string;
  file_name: string;
  provider_used: string;
  extraction_status: string;
  confidence: number;
  fields: Record<string, unknown>;
  tables: OcrTable[];
  validation_issues: string[];
  raw_text_excerpt: string;
};

export type DocumentOcrSummary = {
  document_count: number;
  customer_count: number;
  extracted_field_count: number;
  expected_field_count: number;
  field_accuracy: number;
  table_row_recall: number;
  average_confidence: number;
  fallback_count: number;
  timeout_count: number;
  warning_count: number;
  provider_used: string;
};

export type DocumentOcrPayload = {
  summary: DocumentOcrSummary;
  documents: DocumentExtraction[];
};

export type SupportKnowledgeChunk = {
  chunk_id: string;
  source_id: string;
  source_file: string;
  source_type: string;
  topic: string;
  title: string;
  text: string;
  char_start: number;
  char_end: number;
  checksum: string;
};

export type SupportChatbotSource = {
  source_id: string;
  source_file: string;
  chunk_id: string;
  title: string;
  quote: string;
  score: number;
};

export type SupportChatbotAnswer = {
  question_id?: string | null;
  question: string;
  answer: string;
  answer_status: string;
  provider_used: string;
  model_name: string;
  confidence: number;
  retrieval_confidence: number;
  sources: SupportChatbotSource[];
  escalation_required: boolean;
  escalation_reason?: string | null;
  policy_tags: string[];
  missing_information: string[];
  warnings: string[];
};

export type SupportChatbotSummary = {
  question_count: number;
  answered_count: number;
  citation_accuracy: number;
  source_recall: number;
  average_confidence: number;
  fallback_count: number;
  timeout_count: number;
  invalid_json_count: number;
  escalation_count: number;
  warning_count: number;
  provider_used: string;
};

export type SupportChatbotPayload = {
  summary: SupportChatbotSummary;
  answers: SupportChatbotAnswer[];
  retrieved_chunks: SupportKnowledgeChunk[];
};

export type SupportChatRequest = {
  question: string;
};

export type SupportChatResponse = {
  run: ModelRun;
  result: ProcessedResult;
  payload: SupportChatbotPayload;
};

export type LiquidityLocationProfile = {
  series_id: string;
  location_name: string;
  location_type: string;
  region: string;
  history_days: number;
  recent_average_demand: number;
  recent_peak_demand: number;
  last_closing_cash: number;
  cash_capacity: number;
  minimum_cash_threshold: number;
};

export type LiquidityCalendarEvent = {
  event_id: string;
  event_type: string;
  name: string;
  start_date: string;
  end_date: string;
  impact_multiplier: number;
  affected_location_type: string;
  affected_region: string;
};

export type LiquidityForecastRecord = {
  forecast_id: string;
  series_id: string;
  location_id: string;
  location_name: string;
  location_type: string;
  region: string;
  date: string;
  horizon_step: number;
  actual_net_cash_demand?: number | null;
  predicted_mean: number;
  predicted_p10: number;
  predicted_p50: number;
  predicted_p90: number;
  absolute_error?: number | null;
  stockout_risk: number;
  recommended_replenishment: number;
  projected_closing_cash: number;
  reason_codes: string[];
};

export type LiquidityForecastSummary = {
  series_count: number;
  history_days: number;
  forecast_horizon_days: number;
  forecast_count: number;
  provider_used: string;
  model_name: string;
  mae: number;
  rmse: number;
  mape: number;
  p10_p90_coverage: number;
  average_stockout_risk: number;
  high_risk_forecast_count: number;
  recommended_replenishment_total: number;
  fallback_count: number;
  timeout_count: number;
  warning_count: number;
};

export type LiquidityForecastPayload = {
  summary: LiquidityForecastSummary;
  forecasts: LiquidityForecastRecord[];
  series_profiles: LiquidityLocationProfile[];
  calendar_events: LiquidityCalendarEvent[];
  warnings: string[];
};

export type ConfusionMatrix = {
  tp: number;
  tn: number;
  fp: number;
  fn: number;
};

export type RocPoint = {
  threshold: number;
  tpr: number;
  fpr: number;
};

export type PrPoint = {
  threshold: number;
  precision: number;
  recall: number;
};

export type SplitEvaluation = {
  split: string;
  record_count: number;
  primary_metric?: string;
  primary_metric_label?: string;
  primary_score?: number | null;
  pr_auc?: number | null;
  precision?: number;
  recall?: number;
  f1?: number;
  accuracy: number;
  roc_auc?: number | null;
  threshold: number;
  correct_predictions: number;
  confusion_matrix: ConfusionMatrix;
  pr_curve?: PrPoint[];
  roc_curve: RocPoint[];
  records: DecisionRecord[];
};

export type ProcessedResult = {
  id: string;
  run_id: string;
  use_case_slug: string;
  result_type: string;
  payload: {
    split?: string;
    evaluation?: SplitEvaluation;
    records?: DecisionRecord[];
    summary?: DocumentOcrSummary | SupportChatbotSummary | LiquidityForecastSummary | AmlMonitoringSummary | KycKybSummary | EmailAutomationSummary | MarketIntelligenceSummary;
    documents?: DocumentExtraction[];
    answers?: SupportChatbotAnswer[];
    retrieved_chunks?: SupportKnowledgeChunk[];
    forecasts?: LiquidityForecastRecord[];
    series_profiles?: LiquidityLocationProfile[];
    calendar_events?: LiquidityCalendarEvent[];
    alerts?: AmlAlertDecision[];
    narratives?: AmlNarrativeDraft[];
    network_summary?: AmlNetworkSummary;
    case_note_summary?: AmlCaseNoteSummary;
    packages?: Record<string, unknown>[];
    extracted_documents?: KycKybExtractedDocument[];
    rule_findings?: KycKybRuleFinding[];
    risk_decisions?: KycKybPackageDecision[];
    drafts?: EmailAutomationDraft[];
    compliance_findings?: EmailComplianceFinding[];
    scores?: EmailAutomationScore[];
    briefs?: MarketBrief[];
    signals?: MarketSignal[];
    sources?: MarketSource[];
    evidence_items?: MarketEvidenceItem[];
    query_plan?: Record<string, unknown>[];
    agent_trace?: MarketAgentStep[];
    cost_control?: MarketCostControl;
    warnings?: string[];
  };
  explanation: Record<string, unknown>;
  created_at: string;
};

export type TrainingStatus = {
  use_case_slug: string;
  title?: string;
  order?: number;
  status: "idle" | "queued" | "running" | "completed" | "failed" | "skipped";
  progress_percent: number;
  stage: string;
  training_run_id: string | null;
  error: string | null;
};

export type StartupStatus = {
  ready: boolean;
  ml_training_ready: boolean;
  ml_phase: string;
  skip_startup_training: boolean;
  active_stage: TrainingStatus | null;
  completed_stage_count: number;
  total_stage_count: number;
  stages: TrainingStatus[];
};

export type EvaluationBundle = {
  run: ModelRun;
  result: ProcessedResult;
  evaluation: SplitEvaluation;
  payload?: AmlMonitoringPayload | KycKybPayload;
};

export type EvaluationsResponse = {
  use_case_slug: string;
  val: EvaluationBundle | null;
  test: EvaluationBundle | null;
};

export type DocumentOcrLatestResponse = {
  use_case_slug: string;
  latest: {
    run: ModelRun;
    result: ProcessedResult;
    payload: DocumentOcrPayload;
  } | null;
};

export type SupportChatbotLatestResponse = {
  use_case_slug: string;
  latest: {
    run: ModelRun;
    result: ProcessedResult;
    payload: SupportChatbotPayload;
  } | null;
  latest_chat: {
    run: ModelRun;
    result: ProcessedResult;
    payload: SupportChatbotPayload;
  } | null;
};

export type LiquidityForecastLatestResponse = {
  use_case_slug: string;
  latest: {
    run: ModelRun;
    result: ProcessedResult;
    payload: LiquidityForecastPayload;
  } | null;
};

export type AmlMonitoringLatestResponse = {
  use_case_slug: string;
  val: (EvaluationBundle & { payload: AmlMonitoringPayload }) | null;
  test: (EvaluationBundle & { payload: AmlMonitoringPayload }) | null;
};

export type KycKybLatestResponse = {
  use_case_slug: string;
  val: (EvaluationBundle & { payload: KycKybPayload }) | null;
  test: (EvaluationBundle & { payload: KycKybPayload }) | null;
};

export type EmailAutomationLatestResponse = {
  use_case_slug: string;
  latest: {
    run: ModelRun;
    result: ProcessedResult;
    payload: EmailAutomationPayload;
  } | null;
  latest_draft: {
    run: ModelRun;
    result: ProcessedResult;
    payload: EmailAutomationPayload;
  } | null;
};

export type MarketIntelligenceLatestResponse = {
  use_case_slug: string;
  latest: {
    run: ModelRun;
    result: ProcessedResult;
    payload: MarketIntelligencePayload;
  } | null;
  latest_research: {
    run: ModelRun;
    result: ProcessedResult;
    payload: MarketIntelligencePayload;
  } | null;
};

export type FraudEvaluationBundle = EvaluationBundle;
export type FraudEvaluationsResponse = EvaluationsResponse;

export type RunProgress = {
  run_id: string;
  status: string;
  progress_percent: number;
  stage: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    if (typeof detail === "object" && detail?.message) {
      throw new Error(`${detail.message}${detail.setup_hint ? ` ${detail.setup_hint}` : ""}`);
    }
    throw new Error(typeof detail === "string" ? detail : `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchUseCases() {
  return request<{ items: UseCase[] }>("/use-cases");
}

export function fetchAiHealth() {
  return request<{
    adapters: {
      name: string;
      available: boolean;
      provider: string;
      model_name: string | null;
      message: string;
      setup_hint?: string | null;
    }[];
  }>("/ai/health");
}

export function fetchRawData(slug: string) {
  return request<{ datasets: RawDataset[]; artifacts: RawArtifact[] }>(`/use-cases/${slug}/raw`);
}

export function fetchTrainingStatus(slug: string) {
  return request<TrainingStatus>(`/use-cases/${slug}/training-status`);
}

export function fetchStartupStatus() {
  return request<StartupStatus>("/startup/status");
}

export function fetchUseCaseEvaluations(slug: string) {
  return request<EvaluationsResponse>(`/use-cases/${slug}/evaluations`);
}

export function fetchDocumentOcrLatest() {
  return request<DocumentOcrLatestResponse>("/use-cases/document-ocr/evaluations");
}

export function fetchSupportChatbotLatest() {
  return request<SupportChatbotLatestResponse>("/use-cases/support-chatbot/evaluations");
}

export function fetchLiquidityForecastLatest() {
  return request<LiquidityForecastLatestResponse>("/use-cases/liquidity-forecast/evaluations");
}

export function fetchAmlMonitoringLatest() {
  return request<AmlMonitoringLatestResponse>("/use-cases/aml-monitoring/evaluations");
}

export function fetchKycKybLatest() {
  return request<KycKybLatestResponse>("/use-cases/kyc-kyb/evaluations");
}

export function fetchEmailAutomationLatest() {
  return request<EmailAutomationLatestResponse>("/use-cases/email-automation/evaluations");
}

export function fetchMarketIntelligenceLatest() {
  return request<MarketIntelligenceLatestResponse>("/use-cases/market-intelligence/evaluations");
}

export function submitSupportChatbotQuestion(payload: SupportChatRequest) {
  return request<SupportChatResponse>("/use-cases/support-chatbot/chat", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function submitEmailDraft(payload: EmailDraftRequest) {
  return request<EmailDraftResponse>("/use-cases/email-automation/draft", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function submitMarketResearch(payload: MarketResearchRequest) {
  return request<MarketResearchResponse>("/use-cases/market-intelligence/research", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchFraudEvaluations(slug: string) {
  return fetchUseCaseEvaluations(slug);
}

export function fetchRuns(slug: string) {
  return request<{ items: ModelRun[] }>(`/use-cases/${slug}/runs`);
}

export function startUseCaseRun(slug: string) {
  return request<{ run_id: string; status: string }>(`/use-cases/${slug}/run`, { method: "POST" });
}

export function startFraudRun(slug: string) {
  return startUseCaseRun(slug);
}

export function fetchRunProgress(slug: string, runId: string) {
  return request<RunProgress>(`/use-cases/${slug}/runs/${runId}/progress`);
}

export function fetchRunResult(slug: string, runId: string) {
  return request<{ run: ModelRun; result: ProcessedResult }>(`/use-cases/${slug}/runs/${runId}/result`);
}

export function fetchRunDetail(slug: string, runId: string) {
  return request<{ run: ModelRun; results: ProcessedResult[] }>(`/use-cases/${slug}/runs/${runId}`);
}

export async function runUseCaseWithProgress(
  slug: string,
  onProgress: (progress: RunProgress) => void,
  failureMessage = "Use case run failed."
): Promise<{ run: ModelRun; result: ProcessedResult }> {
  const started = await startUseCaseRun(slug);
  const runId = started.run_id;

  for (;;) {
    const progress = await fetchRunProgress(slug, runId);
    onProgress(progress);
    if (progress.status === "completed") {
      return fetchRunResult(slug, runId);
    }
    if (progress.status === "failed") {
      const detail = await fetchRunDetail(slug, runId).catch(() => null);
      const message = detail?.run.error_message ?? failureMessage;
      throw new Error(message);
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
}

export async function runFraudUseCaseWithProgress(
  slug: string,
  onProgress: (progress: RunProgress) => void
): Promise<{ run: ModelRun; result: ProcessedResult }> {
  return runUseCaseWithProgress(slug, onProgress, "Fraud model run failed.");
}
