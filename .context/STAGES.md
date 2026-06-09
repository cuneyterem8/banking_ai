# STAGES.md - Banking AI Portal: 10 Use Case Details

> **AI INSTRUCTION**: Read this file when working on a specific stage or when you need stage-specific technical details. This is the deep-dive companion to CONTEXT.md.

---

## Stage Registry Summary

| # | Use Case | Slug | Category | Adapter | Model Family | Primary Metric |
|---|----------|------|----------|---------|-------------|----------------|
| 1 | Fraud Detection | `fraud-detection` | Risk Operations | `autogluon-tabular` | Classification | PR-AUC |
| 2 | Credit Risk | `credit-risk` | Lending | `autogluon-tabular` | Classification+Regression | ROC-AUC |
| 3 | Document OCR | `document-ocr` | Document Intelligence | `ocr-local-gpt4o-fallback` | Document Extraction | Field Accuracy |
| 4 | Support Chatbot | `support-chatbot` | Customer Operations | `ollama-qwen-gpt4o-fallback` | RAG | Citation Accuracy |
| 5 | Liquidity Forecast | `liquidity-forecast` | Treasury Operations | `autogluon-timeseries` | Time Series | MAE/RMSE/MAPE |
| 6 | AML Monitoring | `aml-monitoring` | Compliance | `autogluon-tabular-local-llm-gpt4o-fallback` | Risk Scoring+Reporting | PR-AUC |
| 7 | KYC/KYB | `kyc-kyb` | Onboarding | `ocr-rules-autogluon-gpt4o-fallback` | Document+Risk Scoring | PR-AUC |
| 8 | Email Automation | `email-automation` | Customer Communications | `template-rules-ollama-gpt4o-fallback` | Draft Generation | Quality Score |
| 9 | Market Intelligence | `market-intelligence` | Research | `multi-agent-openai-web-search` | Agentic Research | Signal Confidence |
| 10 | Workflow Orchestration | `workflow-orchestration` | Process Automation | `deterministic-dag-orchestrator` | Workflow Orchestration | Straight-Through Rate |

---

## Stage 1: Fraud Detection

### Overview
Binary classification of synthetic card/transfer transactions for fraud probability.

### Data
- **Train**: 2,560 records (64%)
- **Validation**: 640 records (16%)
- **Test**: 800 records (20%)
- **Total**: 4,000 synthetic transactions
- **Features**: 27 engineered features (device, IP, merchant risk, velocity, authentication, geography, etc.)

### Backend Files
- `backend/app/use_cases/fraud_detection/training.py` — AutoGluon training logic
- `backend/app/use_cases/fraud_detection/threshold_tuning.py` — Optimal threshold calibration
- `backend/app/use_cases/fraud_detection/metrics.py` — Evaluation metrics (PR-AUC, precision, recall, F1, confusion matrix)
- `backend/app/use_cases/fraud_detection/feature_engineering.py` — 27 feature generation
- `backend/app/use_cases/fraud_detection/data_generation.py` — Synthetic transaction generation
- `backend/app/use_cases/fraud_detection/raw_data.py` — Data loading (train/val/test)
- `backend/app/use_cases/fraud_detection/service.py` — Run orchestration + persistence
- `backend/app/use_cases/fraud_detection/schemas.py` — Pydantic models
- `backend/app/use_cases/fraud_detection/data_leakage.py` — Data leakage prevention
- `backend/app/use_cases/fraud_detection/risk_prior.py` — Risk prior calculation
- `backend/app/use_cases/fraud_detection/train_calibration.py` — Training calibration

### Frontend Component
- `frontend/src/App.tsx` → `FraudDetectionPage()`

### UI Elements
- Metric cards: Train/Val/Test record counts, Training Status
- **Overview Panel**: Fraud overview statistics
- **Raw Artifacts Panel**: List of raw XLSX files
- **Run Adapter Panel**: "Run Fraud Model" button + progress bar
- **Validation Metrics Panel**: PR-AUC, precision/recall, confusion matrix, ROC/PR curves
- **Validation Predictions Table**: Per-transaction fraud probability, risk level, decision
- **Test Evaluation Panel**: Same metrics for test split
- **Test Predictions Table**: Held-out test predictions
- **Run History Panel**: List of all runs

### API Endpoints
- `GET /api/use-cases/fraud-detection/raw` — Raw datasets + artifacts
- `GET /api/use-cases/fraud-detection/training-status` — Startup training status
- `GET /api/use-cases/fraud-detection/evaluations` — Val + test evaluation bundles
- `POST /api/use-cases/fraud-detection/run` — Trigger test run
- `GET /api/use-cases/fraud-detection/runs` — List all runs
- `GET /api/use-cases/fraud-detection/runs/{run_id}/progress` — Real-time progress
- `GET /api/use-cases/fraud-detection/runs/{run_id}/result` — Final result

### Startup Flow
1. Reset fraud outputs from database
2. Clear existing AutoGluon model directory
3. Load train (2,560) and val (640) transactions
4. Train AutoGluon TabularPredictor on train
5. Calibrate threshold on val
6. Save validation metrics to database
 7. Persist model artifact to `backend/models/fraud-detection/autogluon`

### User Run Flow
1. Load test transactions (800)
2. Load trained model
3. Score test split
4. Evaluate predictions (PR-AUC, precision, recall, F1, confusion matrix)
5. Save results to database

### Key Schema Types
- `FraudDecision` — Per-transaction decision record
- `SplitEvaluation` — Evaluation metrics bundle
- `ConfusionMatrix`, `RocPoint`, `PrPoint` — Chart data

### Data Directory
- `data/fraud_detection/raw/train/` — `fraud_train.xlsx`
- `data/fraud_detection/raw/val/` — `fraud_val.xlsx`
- `data/fraud_detection/raw/test/` — `fraud_test.xlsx`

---

## Stage 2: Credit Risk

### Overview
Probability-of-default scoring for synthetic loan applications with recommended credit limit.

### Data
- **Train**: 1,920 applications (64%)
- **Validation**: 480 applications (16%)
- **Test**: 600 applications (20%)
- **Total**: 3,000 synthetic applications
- **Fields**: 23 applicant/underwriting fields + synthetic loss-given-default + label

### Backend Files
- `backend/app/use_cases/credit_risk/training.py` — Training logic
- `backend/app/use_cases/credit_risk/threshold_tuning.py` — Threshold calibration
- `backend/app/use_cases/credit_risk/metrics.py` — Evaluation metrics (ROC-AUC, PR-AUC, precision, recall, F1)
- `backend/app/use_cases/credit_risk/feature_engineering.py` — Feature generation
- `backend/app/use_cases/credit_risk/data_generation.py` — Synthetic application generation
- `backend/app/use_cases/credit_risk/raw_data.py` — Data loading
- `backend/app/use_cases/credit_risk/service.py` — Run orchestration
- `backend/app/use_cases/credit_risk/schemas.py` — Pydantic models
- `backend/app/use_cases/credit_risk/data_leakage.py` — Leakage prevention
- `backend/app/use_cases/credit_risk/risk_prior.py` — Risk prior calculation

### Frontend Component
- `frontend/src/App.tsx` → `CreditRiskPage()`

### UI Elements
- Metric cards: Train/Val/Test counts, Training Status
- **Overview Panel**: Default statistics by split
- **Raw Artifacts Panel**: Raw XLSX files
- **Run Adapter Panel**: "Run Credit Risk Model" button
- **Validation Metrics Panel**: ROC-AUC, PR-AUC, precision/recall, confusion matrix
- **Validation Decisions Table**: Per-application PD probability, risk grade (A-E), recommended limit, expected loss
- **Test Evaluation Panel**: Same metrics for test split
- **Test Decisions Table**: Held-out test predictions
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/credit-risk/raw` — Raw datasets + artifacts
- `GET /api/use-cases/credit-risk/training-status` — Startup status
- `GET /api/use-cases/credit-risk/evaluations` — Val + test bundles
- `POST /api/use-cases/credit-risk/run` — Trigger test run
- `GET /api/use-cases/credit-risk/runs` — List runs
- `GET /api/use-cases/credit-risk/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/credit-risk/runs/{run_id}/result` — Result

### Startup Flow
1. Reset credit outputs
2. Clear AutoGluon model
3. Load train (1,920) and val (480)
4. Train AutoGluon TabularPredictor
5. Calibrate threshold on val
6. Save validation metrics
 7. Persist model to `backend/models/credit-risk/autogluon`

### User Run Flow
1. Load test applications (600)
2. Load trained model
3. Score test split
4. Evaluate (ROC-AUC, PR-AUC, precision, recall, F1)
5. Save results

### Key Schema Types
- `CreditDecision` — Per-application decision (risk grade, recommended limit, expected loss)

### Data Directory
- `data/credit_risk/raw/train/` — `credit_train.xlsx`
- `data/credit_risk/raw/val/` — `credit_val.xlsx`
- `data/credit_risk/raw/test/` — `credit_test.xlsx`

---

## Stage 3: Document OCR

### Overview
Structured extraction from synthetic banking documents (PDF, scanned PDF, JPG).

### Data
- **12 customer packages** (customer_0001 through customer_0012)
- **60 documents total**:
  - 36 digital PDFs (bank_statement, account_confirmation, income_proof)
  - 12 scanned PDFs (scanned_statement)
  - 12 JPG transfer notices

### Backend Files
- `backend/app/use_cases/document_ocr/extraction.py` — OCR logic (pdfplumber + PyMuPDF)
- `backend/app/use_cases/document_ocr/data_generation.py` — Synthetic document generation
- `backend/app/use_cases/document_ocr/raw_data.py` — Document loading + manifest
- `backend/app/use_cases/document_ocr/service.py` — Run orchestration
- `backend/app/use_cases/document_ocr/schemas.py` — Pydantic models
- `backend/app/ai/ocr_adapter.py` — OCR adapter + GPT-4o fallback

### Frontend Component
- `frontend/src/App.tsx` → `DocumentOcrPage()`

### UI Elements
- Metric cards: Customers, Documents, Raw Artifacts, Latest Provider
- **Overview Panel**: Document type distribution
- **Raw Manifest Panel**: Manifest preview table
- **Adapter Health Panel**: Local OCR + GPT-4o status
- **Raw Artifacts by Customer**: Grouped file list
- **Run Adapter Panel**: "Run Document OCR" button
- **Latest Extraction Summary**: Provider, fallbacks, field accuracy, table recall, avg confidence, warnings
- **Document Results Table**: Per-document extraction status, confidence, field count
- **Selected Document Detail**: Field table, raw text excerpt, validation issues
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/document-ocr/raw` — Raw datasets + artifacts
- `GET /api/use-cases/document-ocr/training-status` — Startup status
- `GET /api/use-cases/document-ocr/evaluations` — Latest extraction
- `POST /api/use-cases/document-ocr/run` — Trigger extraction
- `GET /api/use-cases/document-ocr/runs` — List runs
- `GET /api/use-cases/document-ocr/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/document-ocr/runs/{run_id}/result` — Result

### Startup Flow
1. Load all 60 documents from `data/document_ocr/raw/customer_*/`
2. For each document:
   - Try pdfplumber/PyMuPDF for text-based PDFs
   - Try GPT-4o for scanned/image-only (if API key set)
   - Extract fields, tables, text excerpts
3. Calculate field accuracy vs ground_truth.json
4. Persist extraction results

### User Run Flow
1. Re-run extraction over all documents
2. Same logic as startup but saved as a new run

### Key Schema Types
- `DocumentExtraction` — Per-document extraction (fields, tables, confidence, validation issues)
- `DocumentOcrSummary` — Overall metrics (field_accuracy, table_row_recall, average_confidence)

### Data Directory
- `data/document_ocr/raw/customer_0001/` through `customer_0012/`
  - `bank_statement.pdf`
  - `account_confirmation.pdf`
  - `income_proof.pdf`
  - `scanned_statement.pdf`
  - `transfer_notice.jpg`
- `data/document_ocr/metadata.json` — Manifest + checksums
- `data/document_ocr/ground_truth.json` — Expected fields and table rows

---

## Stage 4: Support Chatbot

### Overview
Local-first RAG assistant for synthetic branch/contact-center support policies.

### Data
- **8 knowledge documents** (policies, procedures, FAQs, notices)
- **26 deterministic BM25 chunks**
- **8 evaluation questions** (deterministic)

### Backend Files
- `backend/app/use_cases/support_chatbot/retrieval.py` — BM25 retrieval over knowledge base
- `backend/app/use_cases/support_chatbot/llm_service.py` — Answer generation (Ollama + GPT-4o fallback)
- `backend/app/use_cases/support_chatbot/data_generation.py` — Knowledge base generation
- `backend/app/use_cases/support_chatbot/raw_data.py` — Knowledge loading
- `backend/app/use_cases/support_chatbot/service.py` — Evaluation + chat orchestration
- `backend/app/use_cases/support_chatbot/schemas.py` — Pydantic models
- `backend/app/ai/ollama_qwen_adapter.py` — Ollama adapter
- `backend/app/ai/openai_gpt4o_adapter.py` — OpenAI fallback

### Frontend Component
- `frontend/src/App.tsx` → `SupportChatbotPage()`

### UI Elements
- Metric cards: Knowledge Documents, Chunks, Evaluation Questions, Latest Provider
- **Overview Panel**: Knowledge base coverage
- **Raw Knowledge Base Panel**: Document list by type (policies, procedures, FAQ, notices)
- **Adapter Health Panel**: Ollama Qwen + GPT-4o status
- **Chat Workspace Panel**: Question textarea + "Ask Support Chatbot" button
  - Answer card with answer text, confidence, citations
  - Source list with clickable chunk IDs
- **Source Detail Panel**: Selected chunk text + metadata
- **Evaluation Runner Panel**: "Run Support Evaluation" button
  - Evaluation metrics: Provider, Answered count, Citation Accuracy, Source Recall, Avg Confidence, Fallbacks
  - Evaluation table: Question, answer, status, confidence, sources
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/support-chatbot/raw` — Raw datasets + artifacts
- `GET /api/use-cases/support-chatbot/training-status` — Startup status
- `GET /api/use-cases/support-chatbot/evaluations` — Latest evaluation + chat
- `POST /api/use-cases/support-chatbot/run` — Run evaluation
- `POST /api/use-cases/support-chatbot/chat` — Ask a custom question
- `GET /api/use-cases/support-chatbot/runs` — List runs
- `GET /api/use-cases/support-chatbot/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/support-chatbot/runs/{run_id}/result` — Result

### Startup Flow
1. Load 8 knowledge documents into chunks
2. Run BM25 retrieval over all 8 evaluation questions
3. Generate answers using Ollama Qwen (or GPT-4o fallback)
4. Calculate citation accuracy and source recall vs ground truth
5. Persist evaluation results

### User Actions
- **"Ask Support Chatbot"**: Type custom question → BM25 retrieval → LLM answer with citations
- **"Run Support Evaluation"**: Re-run deterministic evaluation set

### Key Schema Types
- `SupportChatbotAnswer` — Per-question answer (text, confidence, sources, escalation)
- `SupportChatbotSummary` — Evaluation metrics (citation_accuracy, source_recall, average_confidence)
- `SupportKnowledgeChunk` — Retrieved chunk (text, source, topic, score)

### Data Directory
- `data/support_chatbot/raw/policies/` — PDF policy documents
- `data/support_chatbot/raw/procedures/` — Markdown procedures
- `data/support_chatbot/raw/faq/` — FAQ JSON files
- `data/support_chatbot/raw/notices/` — Product notice TXT files
- `data/support_chatbot/raw/evaluation/` — Evaluation questions JSON
- `data/support_chatbot/metadata.json` — Knowledge manifest
- `data/support_chatbot/ground_truth.json` — Expected sources and citations

---

## Stage 5: Liquidity Forecast

### Overview
Forecast synthetic branch/ATM cash demand with quantile outputs (p10, p50, p90).

### Data
- **6 branch/ATM series**
- **180 history days**
- **14 holdout forecast days**
- **Holiday/campaign calendars** (CSV)
- **Cash inventory policy** (PDF)

### Backend Files
- `backend/app/use_cases/liquidity_forecast/forecasting.py` — TimeSeries forecasting + baseline fallback
- `backend/app/use_cases/liquidity_forecast/data_generation.py` — Synthetic cash demand generation
- `backend/app/use_cases/liquidity_forecast/raw_data.py` — Time series loading
- `backend/app/use_cases/liquidity_forecast/service.py` — Run orchestration
- `backend/app/use_cases/liquidity_forecast/schemas.py` — Pydantic models
- `backend/app/ai/autogluon_timeseries_adapter.py` — AutoGluon TimeSeries adapter

### Frontend Component
- `frontend/src/App.tsx` → `LiquidityForecastPage()`

### UI Elements
- Metric cards: Series, History Days, Forecast Horizon, Latest Provider
- **Overview Panel**: Location profiles (branch/ATM)
- **Raw Data Panel**: Time series preview + calendar events
- **Adapter Health Panel**: AutoGluon TimeSeries status
- **Run Adapter Panel**: "Run Liquidity Forecast" button
- **Latest Forecast Summary**: Provider, MAE, RMSE, MAPE, p10-p90 coverage, stockout risk, replenishment total
- **Forecast Chart**: History + forecast line chart with quantile bands
- **Forecast Table**: Per-date predictions (mean, p10, p50, p90, stockout risk, replenishment)
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/liquidity-forecast/raw` — Raw datasets + artifacts
- `GET /api/use-cases/liquidity-forecast/training-status` — Startup status
- `GET /api/use-cases/liquidity-forecast/evaluations` — Latest forecast
- `POST /api/use-cases/liquidity-forecast/run` — Trigger forecast
- `GET /api/use-cases/liquidity-forecast/runs` — List runs
- `GET /api/use-cases/liquidity-forecast/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/liquidity-forecast/runs/{run_id}/result` — Result

### Startup Flow
1. Load 6 time series (180 days history)
2. Load calendar events (holidays, campaigns)
3. Try AutoGluon TimeSeries predictor
4. If unavailable, use deterministic seasonal baseline
5. Generate 14-day forecasts with quantiles
6. Evaluate vs holdout actuals
7. Persist results

### User Run Flow
1. Re-run forecast over same data
2. Same logic as startup

### Key Schema Types
- `LiquidityForecastRecord` — Per-date forecast (mean, p10, p50, p90, stockout_risk, replenishment)
- `LiquidityForecastSummary` — Overall metrics (MAE, RMSE, MAPE, coverage, avg_stockout_risk)
- `LiquidityLocationProfile` — Series metadata (location, capacity, threshold, recent demand)
- `LiquidityCalendarEvent` — Event (holiday, campaign, multiplier)

### Data Directory
- `data/liquidity_forecast/raw/timeseries/` — Cash time-series Excel
- `data/liquidity_forecast/raw/calendar/` — Holiday/campaign CSV
- `data/liquidity_forecast/raw/policies/` — Cash inventory policy PDF
- `data/liquidity_forecast/metadata.json` — Series manifest
- `data/liquidity_forecast/ground_truth.json` — Holdout actuals

---

## Stage 6: AML Monitoring

### Overview
Prioritize synthetic AML alerts and draft suspicious activity narratives (SAR).

### Data
- **2,500 synthetic alerts**
- **Transaction network sheets** (Excel)
- **Entity relationships** (JSON)
- **Suspicious activity notes** (PDF)
- **Typology labels + SAR ground truth**
- **Train**: 1,600 / **Val**: 400 / **Test**: 500

### Backend Files
- `backend/app/use_cases/aml_monitoring/training.py` — AutoGluon training
- `backend/app/use_cases/aml_monitoring/threshold_tuning.py` — Threshold calibration
- `backend/app/use_cases/aml_monitoring/metrics.py` — Evaluation metrics (PR-AUC)
- `backend/app/use_cases/aml_monitoring/feature_engineering.py` — Feature generation
- `backend/app/use_cases/aml_monitoring/llm_service.py` — SAR narrative generation
- `backend/app/use_cases/aml_monitoring/data_generation.py` — Synthetic alert generation
- `backend/app/use_cases/aml_monitoring/raw_data.py` — Alert loading
- `backend/app/use_cases/aml_monitoring/service.py` — Run orchestration
- `backend/app/use_cases/aml_monitoring/schemas.py` — Pydantic models

### Frontend Component
- `frontend/src/App.tsx` → `AmlMonitoringPage()`

### UI Elements
- Metric cards: Train/Val/Test Alerts, Training Status, Latest Provider
- **Overview Panel**: Alert distribution by typology
- **Raw Data Panel**: Alert preview + network summary
- **Adapter Health Panel**: AutoGluon + Local LLM + GPT-4o status
- **Run Adapter Panel**: "Run AML Monitoring" button
- **Validation Metrics Panel**: PR-AUC, precision, recall, F1, confusion matrix
- **Validation Alerts Table**: Per-alert SAR probability, risk level, top factors
- **Test Evaluation Panel**: Same metrics for test
- **Test Alerts Table**: Highest-risk test alerts
- **Narrative Drafts Panel**: SAR narratives (summary, evidence bullets, recommended next steps)
- **Network Summary Panel**: Account/counterparty counts, cluster counts, high-risk jurisdictions
- **Case Note Summary Panel**: Note count, escalation topics, guidance excerpt
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/aml-monitoring/raw` — Raw datasets + artifacts
- `GET /api/use-cases/aml-monitoring/training-status` — Startup status
- `GET /api/use-cases/aml-monitoring/evaluations` — Val + test bundles
- `POST /api/use-cases/aml-monitoring/run` — Trigger test run
- `GET /api/use-cases/aml-monitoring/runs` — List runs
- `GET /api/use-cases/aml-monitoring/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/aml-monitoring/runs/{run_id}/result` — Result

### Startup Flow
1. Reset AML outputs
2. Clear AutoGluon model
3. Load train (1,600) and val (400)
4. Train AutoGluon TabularPredictor
5. Calibrate threshold on val
6. Draft top validation narratives using local LLM (Ollama) or GPT-4o
7. Save validation metrics + narratives
8. Persist model

### User Run Flow
1. Load test alerts (500)
2. Load trained model
3. Score test split
4. Draft narratives for highest-risk alerts
5. Evaluate vs ground truth
6. Save results

### Key Schema Types
- `AmlAlertDecision` — Per-alert decision (SAR probability, risk level, top factors, related entities)
- `AmlNarrativeDraft` — SAR narrative (summary, evidence, next steps, confidence)
- `AmlNetworkSummary` — Network stats (accounts, counterparties, clusters, jurisdictions)
- `AmlMonitoringSummary` — Overall metrics (PR-AUC, precision, recall, narrative count)

### Data Directory
- `data/aml_monitoring/raw/train/` — `aml_train.xlsx`
- `data/aml_monitoring/raw/val/` — `aml_val.xlsx`
- `data/aml_monitoring/raw/test/` — `aml_test.xlsx`
- `data/aml_monitoring/raw/network/` — Transaction network Excel
- `data/aml_monitoring/raw/entities/` — Entity relationships JSON
- `data/aml_monitoring/raw/case_notes/` — Case notes PDF
- `data/aml_monitoring/metadata.json` — Alert metadata
- `data/aml_monitoring/ground_truth.json` — SAR labels

---

## Stage 7: KYC/KYB

### Overview
Verify synthetic customer (KYC) and business (KYB) onboarding documents with policy rules.

### Data
- **48 onboarding packages** (individual + business)
- **288 generated documents**
- **Sanctions and jurisdiction reference files**
- **Document policy rules** (PDF)
- **Manual-review ground truth**
- **Train**: 32 / **Val**: 8 / **Test**: 8

### Backend Files
- `backend/app/use_cases/kyc_kyb/extraction.py` — Document extraction (OCR)
- `backend/app/use_cases/kyc_kyb/rules.py` — Deterministic policy rules engine
- `backend/app/use_cases/kyc_kyb/feature_engineering.py` — Feature generation
- `backend/app/use_cases/kyc_kyb/training.py` — AutoGluon training
- `backend/app/use_cases/kyc_kyb/threshold_tuning.py` — Threshold calibration
- `backend/app/use_cases/kyc_kyb/metrics.py` — Evaluation metrics (PR-AUC)
- `backend/app/use_cases/kyc_kyb/llm_service.py` — LLM summary generation
- `backend/app/use_cases/kyc_kyb/data_generation.py` — Synthetic package generation
- `backend/app/use_cases/kyc_kyb/raw_data.py` — Package loading
- `backend/app/use_cases/kyc_kyb/service.py` — Run orchestration
- `backend/app/use_cases/kyc_kyb/schemas.py` — Pydantic models

### Frontend Component
- `frontend/src/App.tsx` → `KycKybPage()`

### UI Elements
- Metric cards: Packages, Individuals, Businesses, Training Status, Latest Provider
- **Overview Panel**: Package type distribution
- **Raw Data Panel**: Package preview + watchlist reference
- **Adapter Health Panel**: OCR + AutoGluon + GPT-4o status
- **Run Adapter Panel**: "Run KYC/KYB Verification" button
- **Validation Metrics Panel**: PR-AUC, precision, recall, F1
- **Validation Packages Table**: Per-package verification status, risk score, missing docs, field mismatches
- **Test Evaluation Panel**: Same metrics for test
- **Test Packages Table**: Held-out test packages
- **Extracted Documents Panel**: Per-document extraction status, confidence, fields
- **Rule Findings Panel**: Policy rule violations (severity, status, evidence)
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/kyc-kyb/raw` — Raw datasets + artifacts
- `GET /api/use-cases/kyc-kyb/training-status` — Startup status
- `GET /api/use-cases/kyc-kyb/evaluations` — Val + test bundles
- `POST /api/use-cases/kyc-kyb/run` — Trigger test run
- `GET /api/use-cases/kyc-kyb/runs` — List runs
- `GET /api/use-cases/kyc-kyb/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/kyc-kyb/runs/{run_id}/result` — Result

### Startup Flow
1. Extract all 288 documents (OCR)
2. Apply deterministic policy rules (sanctions, jurisdiction, missing docs)
3. Train AutoGluon on train (32) with extracted features
4. Calibrate on val (8)
5. Score val, calculate PR-AUC
6. Save results

### User Run Flow
1. Load test packages (8)
2. Extract documents
3. Apply rules
4. Load trained model
5. Score test
6. Evaluate vs ground truth
7. Save results

### Key Schema Types
- `KycKybPackageDecision` — Per-package decision (status, risk score, missing docs, field mismatches)
- `KycKybExtractedDocument` — Per-document extraction (fields, confidence, validation issues)
- `KycKybRuleFinding` — Policy violation (severity, status, evidence)
- `KycKybSummary` — Overall metrics (PR-AUC, precision, recall, hard_rule_count)

### Data Directory
- `data/kyc_kyb/raw/individual/` — Individual packages (PDF, images, Excel)
- `data/kyc_kyb/raw/business/` — Business packages (PDF, images, Excel)
- `data/kyc_kyb/raw/watchlists/` — Sanctions/reference JSON
- `data/kyc_kyb/raw/policies/` — Document policy PDF
- `data/kyc_kyb/metadata.json` — Package manifest
- `data/kyc_kyb/ground_truth.json` — Manual-review labels

---

## Stage 8: Email Automation

### Overview
Generate compliant synthetic customer email and notification drafts (service + campaign).

### Data
- **120 synthetic customers**
- **80 service events**
- **40 campaign audience rows**
- **24 evaluation cases**
- **Compliance policy PDFs**, **brand/tone guidelines**
- **No-send draft ground truth**

### Backend Files
- `backend/app/use_cases/email_automation/template_engine.py` — Template-based draft generation
- `backend/app/use_cases/email_automation/rules.py` — Compliance rule engine
- `backend/app/use_cases/email_automation/scoring.py` — Quality/compliance/personalization scoring
- `backend/app/use_cases/email_automation/llm_service.py` — LLM draft generation (Ollama + GPT-4o)
- `backend/app/use_cases/email_automation/data_generation.py` — Synthetic customer/event generation
- `backend/app/use_cases/email_automation/raw_data.py` — Customer/event loading
- `backend/app/use_cases/email_automation/service.py` — Run + draft orchestration
- `backend/app/use_cases/email_automation/schemas.py` — Pydantic models

### Frontend Component
- `frontend/src/App.tsx` → `EmailAutomationPage()`

### UI Elements
- Metric cards: Customers, Events, Campaigns, Latest Provider
- **Overview Panel**: Draft type distribution
- **Raw Data Panel**: Customer/event preview + templates
- **Adapter Health Panel**: Template engine + Ollama + GPT-4o status
- **Run Adapter Panel**: "Run Email Automation" button
- **Draft Workspace Panel**: Create single draft
  - Select customer, communication type (service/campaign), event type
  - Generated draft: subject, body, preheader, call-to-action
  - Compliance status, risk level, required disclosures
- **Latest Draft Summary**: Draft count, approved/needs-review/rejected, avg quality score, approval rate
- **Drafts Table**: All drafts with quality/compliance/personalization/readability scores
- **Compliance Findings Panel**: Per-draft rule violations
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/email-automation/raw` — Raw datasets + artifacts
- `GET /api/use-cases/email-automation/training-status` — Startup status
- `GET /api/use-cases/email-automation/evaluations` — Latest evaluation + draft
- `POST /api/use-cases/email-automation/run` — Run evaluation
- `POST /api/use-cases/email-automation/draft` — Create single draft
- `GET /api/use-cases/email-automation/runs` — List runs
- `GET /api/use-cases/email-automation/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/email-automation/runs/{run_id}/result` — Result

### Startup Flow
1. Load 24 evaluation cases
2. For each case:
   - Select template or use LLM generation
   - Apply personalization (customer name, event details)
   - Apply compliance rules (disclosures, tone, risk)
   - Score (quality, compliance, personalization, readability)
3. Persist all drafts + scores

### User Actions
- **"Run Email Automation"**: Re-run evaluation set
- **Draft Workspace**: Create single draft (POST /api/use-cases/email-automation/draft)

### Key Schema Types
- `EmailAutomationDraft` — Per-draft (subject, body, preheader, CTA, compliance_status, risk_level)
- `EmailAutomationScore` — Per-draft scores (quality, compliance, personalization, readability)
- `EmailComplianceFinding` — Rule violation (severity, status, evidence)
- `EmailAutomationSummary` — Overall metrics (draft_count, approval_rate, avg_quality_score)

### Data Directory
- `data/email_automation/raw/customers/` — Customer JSON
- `data/email_automation/raw/events/` — Service event JSON
- `data/email_automation/raw/campaigns/` — Campaign Excel
- `data/email_automation/raw/templates/` — Email templates Markdown
- `data/email_automation/raw/policies/` — Compliance policy PDF
- `data/email_automation/raw/evaluation/` — Evaluation cases JSON
- `data/email_automation/metadata.json` — Customer/event manifest
- `data/email_automation/ground_truth.json` — Draft labels

**Important**: No real email sending. Draft-only.

---

## Stage 9: Market Intelligence

### Overview
Budget-controlled multi-agent market research with live web search and cited banking impact briefs.

### Data
- **180 synthetic market articles** (JSON)
- **180 daily rate rows** (CSV)
- **80 competitor rate rows** (Excel)
- **36 economic calendar events** (CSV)
- **8 research brief cases**
- **Topic taxonomy** (JSON)
- **Synthetic market snapshot** (PDF)

### Backend Files
- `backend/app/use_cases/market_intelligence/agents.py` — Multi-agent orchestration
- `backend/app/use_cases/market_intelligence/web_search_service.py` — OpenAI web search API
- `backend/app/use_cases/market_intelligence/signal_scoring.py` — Signal scoring (urgency, confidence, impact)
- `backend/app/use_cases/market_intelligence/source_verification.py` — Source verification + citation tracking
- `backend/app/use_cases/market_intelligence/data_generation.py` — Synthetic market data generation
- `backend/app/use_cases/market_intelligence/raw_data.py` — Market data loading
- `backend/app/use_cases/market_intelligence/service.py` — Brief + research orchestration
- `backend/app/use_cases/market_intelligence/schemas.py` — Pydantic models
- `backend/app/ai/web_search_adapter.py` — Web search adapter

### Frontend Component
- `frontend/src/App.tsx` → `MarketIntelligencePage()`

### UI Elements
- Metric cards: News, Rates, Competitors, Latest Provider
- **Overview Panel**: Market snapshot summary
- **Raw Data Panel**: News preview + rate table + competitor rates
- **Adapter Health Panel**: Web search + OpenAI status
- **Run Adapter Panel**: "Run Market Brief" button
- **Research Workspace Panel**: Scoped research
  - Objective, region, focus areas, depth (quick/standard/deep)
  - Generated brief: headline, executive summary, top developments, banking implications, risks/opportunities, recommended actions, watchlist
  - Clickable source citations with URLs
  - Agent trace: step-by-step execution log
  - Cost control: search call count, estimated cost, budget counter
- **Latest Brief Summary**: Source count, live vs synthetic sources, evidence count, signal count, avg confidence
- **Signals Table**: Per-signal (topic, sector, impact, direction, urgency, confidence)
- **Sources Table**: Per-source (title, domain, snippet, verification status, citation count)
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/market-intelligence/raw` — Raw datasets + artifacts
- `GET /api/use-cases/market-intelligence/training-status` — Startup status
- `GET /api/use-cases/market-intelligence/evaluations` — Latest brief + research
- `POST /api/use-cases/market-intelligence/run` — Run controlled brief
- `POST /api/use-cases/market-intelligence/research` — Run scoped research
- `GET /api/use-cases/market-intelligence/runs` — List runs
- `GET /api/use-cases/market-intelligence/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/market-intelligence/runs/{run_id}/result` — Result

### Startup Flow
1. Run daily banking market brief
2. If `MARKET_LIVE_SEARCH_ENABLED=1` and API key set:
   - Use OpenAI web search API (gpt-5.4-mini)
   - Max 6 search calls (startup limit)
3. Else:
   - Use deterministic synthetic corpus (180 articles)
4. Generate brief with cited sources
5. Track agent steps + cost
6. Persist results

### User Actions
- **"Run Market Brief"**: Re-run controlled brief (max 10 search calls)
- **Research Workspace**: Scoped research (custom objective, max 16 deep calls)

### Key Schema Types
- `MarketBrief` — Brief (headline, summary, developments, implications, risks, actions, watchlist)
- `MarketSignal` — Signal (topic, sector, impact, direction, urgency, confidence)
- `MarketSource` — Source (title, URL, domain, snippet, verification status, citations)
- `MarketAgentStep` — Execution step (agent_name, status, input/output counts, duration)
- `MarketCostControl` — Budget tracking (model, search calls, estimated cost)
- `MarketIntelligenceSummary` — Overall metrics (source_count, signal_count, avg_confidence)

### Data Directory
- `data/market_intelligence/raw/news/` — Market news JSON
- `data/market_intelligence/raw/rates/` — Daily rates CSV
- `data/market_intelligence/raw/competitors/` — Competitor rates Excel
- `data/market_intelligence/raw/calendar/` — Economic calendar CSV
- `data/market_intelligence/raw/snapshot/` — Market snapshot PDF
- `data/market_intelligence/raw/taxonomy/` — Topic taxonomy JSON
- `data/market_intelligence/raw/evaluation/` — Research brief cases JSON
- `data/market_intelligence/metadata.json` — Data manifest
- `data/market_intelligence/ground_truth.json` — Expected briefs

---

## Stage 10: Workflow Orchestration

### Overview
Coordinate synthetic banking cases across persisted outputs from first 9 use cases using deterministic DAGs.

### Data
- **24 synthetic workflow cases**
- **4 workflow types**
- **Case package PDFs/images/Excel/JSON**
- **Dependency contracts** (JSON)
- **SLA policy** (PDF)
- **Startup/held-out evaluation splits**
- **Deterministic routing ground truth**

### Backend Files
- `backend/app/use_cases/workflow_orchestration/workflow_engine.py` — DAG execution engine
- `backend/app/use_cases/workflow_orchestration/decisioning.py` — Routing/SLA decision logic
- `backend/app/use_cases/workflow_orchestration/dependency_loader.py` — Load upstream use case outputs
- `backend/app/use_cases/workflow_orchestration/llm_service.py` — LLM case summaries (Ollama + GPT-4o)
- `backend/app/use_cases/workflow_orchestration/data_generation.py` — Synthetic case generation
- `backend/app/use_cases/workflow_orchestration/raw_data.py` — Case loading
- `backend/app/use_cases/workflow_orchestration/service.py` — Run + orchestrate orchestration
- `backend/app/use_cases/workflow_orchestration/schemas.py` — Pydantic models

### Frontend Component
- `frontend/src/App.tsx` → `WorkflowOrchestrationPage()`

### UI Elements
- Metric cards: Cases, Workflow Types, Latest Provider
- **Overview Panel**: Workflow type distribution
- **Raw Data Panel**: Case preview + dependency contracts
- **Adapter Health Panel**: DAG engine + Ollama + GPT-4o status
- **Run Adapter Panel**: "Run Workflow Batch" button
- **Case Orchestration Workspace Panel**: Single case orchestration
  - Select case ID
  - Execute DAG with dependency checks
  - Generated summary: status, recommended owner, next actions
- **Latest Orchestration Summary**: Case count, straight-through/needs-review/escalated/blocked/rejected, SLA breach count, avg risk score
- **Cases Table**: Per-case (workflow_type, subject, priority, final_status, risk_level, dependency_status)
- **Workflow Steps Table**: Per-step (title, owner, status, dependencies, evidence, blockers)
- **Routing Decisions Table**: Per-case (final_status, recommended_owner, risk_level, straight_through_eligible, manual_review_required)
- **SLA Results Table**: Per-case (policy_hours, elapsed_hours, remaining_hours, SLA status)
- **Case Summaries Table**: LLM-generated summaries (confidence, recommended wording, next steps)
- **Run History Panel**: All runs

### API Endpoints
- `GET /api/use-cases/workflow-orchestration/raw` — Raw datasets + artifacts
- `GET /api/use-cases/workflow-orchestration/training-status` — Startup status
- `GET /api/use-cases/workflow-orchestration/evaluations` — Latest batch + case run
- `POST /api/use-cases/workflow-orchestration/run` — Run batch evaluation
- `POST /api/use-cases/workflow-orchestration/orchestrate` — Orchestrate single case
- `GET /api/use-cases/workflow-orchestration/runs` — List runs
- `GET /api/use-cases/workflow-orchestration/runs/{run_id}/progress` — Progress
- `GET /api/use-cases/workflow-orchestration/runs/{run_id}/result` — Result

### Startup Flow
1. Read latest persisted outputs from first 9 use cases (dependency snapshots)
2. For each startup case (from evaluation split):
   - Load case package
   - Execute workflow DAG
   - Check dependencies (are upstream outputs available?)
   - Apply routing rules (straight-through vs manual review)
   - Apply SLA rules (on track vs breached)
   - Generate LLM summary (optional)
3. Save all case results

### User Actions
- **"Run Workflow Batch"**: Score held-out cases
- **Case Orchestration Workspace**: Persist single selected case

### Key Schema Types
- `WorkflowCaseResult` — Per-case (final_status, risk_level, recommended_owner, next_actions)
- `WorkflowStepResult` — Per-step (status, dependencies, evidence, blockers)
- `WorkflowRoutingDecision` — Routing (straight_through_eligible, manual_review_required, dependency_status)
- `WorkflowSlaResult` — SLA (policy_hours, elapsed_hours, remaining_hours, sla_status)
- `WorkflowCaseSummary` — LLM summary (summary, recommended_wording, next_steps, confidence)
- `WorkflowDependencySnapshot` — Upstream dependency status (available/missing/failed)
- `WorkflowOrchestrationSummary` — Overall metrics (straight_through_count, needs_review_count, sla_breach_count)

### Data Directory
- `data/workflow_orchestration/raw/cases/` — Case packages (PDF, images, Excel, JSON)
- `data/workflow_orchestration/raw/definitions/` — Workflow definitions JSON
- `data/workflow_orchestration/raw/contracts/` — Dependency contracts JSON
- `data/workflow_orchestration/raw/policies/` — SLA policy PDF
- `data/workflow_orchestration/raw/evaluation/` — Evaluation splits JSON
- `data/workflow_orchestration/metadata.json` — Case manifest
- `data/workflow_orchestration/ground_truth.json` — Routing ground truth

**Important**: Does NOT retrain or rerun upstream models. Only reads their latest persisted outputs.

---

## API Endpoint Map

### Health & Status
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Database connectivity check |
| `/api/ready` | GET | API up; ML may still be running |
| `/api/ml-ready` | GET | All startup processing complete |
| `/api/startup/status` | GET | Full pipeline state (all 10 stages) |
| `/api/ai/health` | GET | Adapter readiness (6 adapters) |

### Use Cases (All Stages)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/use-cases` | GET | List all 10 use cases |
| `/api/use-cases/{slug}` | GET | Use case metadata |
| `/api/use-cases/{slug}/raw` | GET | Raw datasets + artifacts |
| `/api/use-cases/{slug}/training-status` | GET | Startup training status |
| `/api/use-cases/{slug}/evaluations` | GET | Latest evaluation bundle |
| `/api/use-cases/{slug}/run` | POST | Trigger user run |
| `/api/use-cases/{slug}/runs` | GET | List all runs |
| `/api/use-cases/{slug}/runs/{run_id}` | GET | Run detail + results |
| `/api/use-cases/{slug}/runs/{run_id}/progress` | GET | Real-time progress |
| `/api/use-cases/{slug}/runs/{run_id}/result` | GET | Final result |

### Special Actions (Per Stage)
| Endpoint | Method | Stage | Action |
|----------|--------|-------|--------|
| `/api/use-cases/support-chatbot/chat` | POST | 4 | Ask custom question |
| `/api/use-cases/email-automation/draft` | POST | 8 | Create single draft |
| `/api/use-cases/market-intelligence/research` | POST | 9 | Run scoped research |
| `/api/use-cases/workflow-orchestration/orchestrate` | POST | 10 | Orchestrate single case |

---

## Database Schema

### Core Tables
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `use_cases` | Registry | `slug` (PK), `title`, `category`, `status`, `implementation_order` |
| `raw_datasets` | Seed metadata | `id`, `use_case_slug`, `dataset_key`, `source_type`, `payload` (JSONB) |
| `raw_artifacts` | File pointers | `id`, `use_case_slug`, `file_name`, `file_path`, `artifact_type`, `metadata_json` (JSONB) |
| `model_runs` | All runs | `id`, `use_case_slug`, `adapter_type`, `provider_used`, `model_name`, `status`, `duration_ms`, `metrics` (JSONB) |
| `processed_results` | ML outputs | `id`, `run_id`, `use_case_slug`, `result_type`, `payload` (JSONB), `explanation` (JSONB) |
| `model_artifacts` | Model paths | `id`, `use_case_slug`, `artifact_type`, `local_path`, `metadata_json` (JSONB) |
| `audit_events` | Audit trail | `id`, `actor`, `action`, `entity_type`, `entity_id`, `metadata_json` (JSONB) |

---

## AI Adapter Map

| Adapter | File | Purpose | Fallback Chain |
|---------|------|---------|---------------|
| AutoGluon Tabular | `app/ai/autogluon_adapter.py` | Fraud, Credit, AML, KYC classification | None (local only) |
| AutoGluon TimeSeries | `app/ai/autogluon_timeseries_adapter.py` | Liquidity forecast | Deterministic baseline |
| Local OCR | `app/ai/ocr_adapter.py` | Document OCR, KYC extraction | GPT-4o |
| Ollama Qwen | `app/ai/ollama_qwen_adapter.py` | Chatbot, Email, Workflow summaries | GPT-4o |
| OpenAI GPT-4o | `app/ai/openai_gpt4o_adapter.py` | Universal fallback | None |
| Web Search | `app/ai/web_search_adapter.py` | Market Intelligence live search | Synthetic corpus |

---

**End of STAGES.md** — For session history, read HISTORY.md. For AI instructions, read AGENTS.md.
