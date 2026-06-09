# Banking AI Portal

**Local-first, staged MVP for 10 banking AI use cases.**

This portal demonstrates real AI/ML operations across ten distinct banking domains using synthetic data, deterministic pipelines, and modular adapters. All app-facing text, source comments, schemas, and synthetic sample content are in English.

![Banking AI Portal Dashboard](image1.png)

---

## 🚀 AI Assistant Prompt

> **For a comprehensive, research-backed first prompt to use with any AI assistant (Claude, Cursor, Copilot, Codex, Qwen, Kimi, etc.), see the `.context/PROMPT.md` file.**

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [The 10 Use Cases (Stages)](#the-10-use-cases-stages)
   - Stage 1: Fraud Detection
   - Stage 2: Credit Risk
   - Stage 3: Document OCR
   - Stage 4: Support Chatbot
   - Stage 5: Liquidity Forecast
   - Stage 6: AML Monitoring
   - Stage 7: KYC/KYB
   - Stage 8: Email Automation
   - Stage 9: Market Intelligence
   - Stage 10: Workflow Orchestration
5. [Data Directory](#data-directory)
6. [Database Schema](#database-schema)
7. [API Endpoint Map](#api-endpoint-map)
8. [AI Adapters & Model Infrastructure](#ai-adapters--model-infrastructure)
9. [Prerequisites](#prerequisites)
10. [Setup Guide](#setup-guide)
11. [Running the Application](#running-the-application)
12. [Startup Pipeline & ML Training](#startup-pipeline--ml-training)
13. [Environment Variables](#environment-variables)
14. [Frontend Structure](#frontend-structure)
15. [Development & Testing](#development--testing)
16. [Troubleshooting](#troubleshooting)
17. [Tips & Best Practices](#tips--best-practices)

---

## Project Overview

The Banking AI Portal is a **local-first** demonstration system designed to showcase how modern AI and ML can be applied to real banking operations. It uses **deterministic synthetic data** for reproducible experiments, persists all artifacts to **PostgreSQL**, and provides a **React-based dashboard** to interact with each use case.

### Key Design Principles

- **Local-first**: Everything runs on your machine (no cloud dependencies except optional OpenAI).
- **Staged MVP**: Each of the 10 use cases is implemented as a discrete stage with its own data, models, and UI.
- **Modular Adapters**: AI backends are abstracted behind adapter interfaces (AutoGluon, Ollama, OpenAI, Local OCR). Fallbacks are automatic.
- **Deterministic Data**: Synthetic datasets are generated via seeded scripts so results are reproducible.
- **PostgreSQL Persistence**: All runs, results, raw artifacts, and evaluations are stored in the database.
- **Queue-based Concurrency**: Heavy ML jobs use a sequential startup queue and a separate user-run queue to avoid resource contention.

### Status

All **10 stages are implemented** and active:

| Stage | Use Case | Category | Status |
|-------|----------|----------|--------|
| 1 | Fraud Detection | Risk Operations | Live |
| 2 | Credit Risk | Lending | Live |
| 3 | Document OCR | Document Intelligence | Live |
| 4 | Support Chatbot | Customer Operations | Live |
| 5 | Liquidity Forecast | Treasury Operations | Live |
| 6 | AML Monitoring | Compliance | Live |
| 7 | KYC/KYB | Onboarding | Live |
| 8 | Email Automation | Customer Communications | Live |
| 9 | Market Intelligence | Research | Live |
| 10 | Workflow Orchestration | Process Automation | Live |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐│
│  │  Dashboard  │  │UseCase Pages│  │Startup Strip│  │  Adapter Health  ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘│
│       http://localhost:5173                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ REST API (CORS)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI + Python)                     │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        API Layer (Routers)                         │ │
│  │  /api/health  /api/ready  /api/ai/health  /api/startup/status      │ │
│  │  /api/use-cases  /api/use-cases/{slug}/raw  /api/use-cases/{slug}/run│ │
│  │  /api/use-cases/{slug}/chat  /api/use-cases/{slug}/draft          │ │
│  │  /api/use-cases/{slug}/research  /api/use-cases/{slug}/orchestrate  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     Services Layer                                  │ │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐ │ │
│  │  │ ML Training     │  │ ML Job Queue     │  │ Run Cleanup /       │ │ │
│  │  │ Manager         │  │ (Startup + User) │  │ Progress Tracking   │ │ │
│  │  └─────────────────┘  └──────────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     Use Case Layer (10 modules)                   │ │
│  │  fraud_detection  credit_risk  document_ocr  support_chatbot      │ │
│  │  liquidity_forecast  aml_monitoring  kyc_kyb  email_automation    │ │
│  │  market_intelligence  workflow_orchestration                      │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     AI Adapter Layer                                │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │ │
│  │  │ AutoGluon  │ │  Ollama    │ │  OpenAI    │ │  Local OCR       │ │ │
│  │  │ Tabular    │ │  Qwen      │ │  GPT-4o    │ │  pdfplumber      │ │ │
│  │  │ TimeSeries │ │            │ │  WebSearch │ │  PyMuPDF         │ │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └──────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     Data / Storage Layer                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐     │ │
│  │  │ PostgreSQL  │  │   data/     │  │   backend/models/       │     │ │
│  │  │ (JSONB)     │  │ (raw files) │  │   (trained models)      │     │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│       http://localhost:8001                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Communication Flow

1. **Frontend** (`http://localhost:5173`) makes REST API calls to the backend.
2. **Backend** (`http://localhost:8001`) serves FastAPI endpoints. On startup, it triggers a **background ML pipeline**.
3. **ML Pipeline** runs 10 stages sequentially in a background thread: Fraud → Credit → OCR → Chatbot → Liquidity → AML → KYC → Email → Market → Workflow.
4. **User Runs** (clicking "Run" buttons) go to a separate **user-run queue** so they don't block startup.
5. **AutoGluon** models share a local lock to prevent Ray/RAM contention.
6. All results are persisted to **PostgreSQL** via **SQLModel**.

---

## Technology Stack

### Backend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Web Framework | **FastAPI** (0.115.6) | High-performance async API |
| Server | **Uvicorn** (0.34.0) | ASGI server |
| ORM / Schema | **SQLModel** (0.0.22) | SQLAlchemy + Pydantic integration |
| Database Driver | **psycopg** (3.2.3) | PostgreSQL driver (binary) |
| Configuration | **pydantic-settings** (2.7.1) | `.env` file configuration |
| ML AutoML | **AutoGluon** (1.5.0) | Tabular + TimeSeries predictor |
| Distributed | **Ray** (2.52.1) | AutoGluon backend |
| Gradient Boosting | **LightGBM, XGBoost, CatBoost** | Ensemble models |
| Local LLM | **Ollama** (Qwen2.5:7b) | On-premise inference |
| Cloud LLM | **OpenAI** (gpt-4o, gpt-5.4-mini) | Cloud fallback |
| Web Search | **OpenAI Web Search API** | Live market research |
| OCR | **pdfplumber, PyMuPDF, pypdf** | PDF text extraction |
| Image | **Pillow** (11.1.0) | Image generation for OCR |
| Data Processing | **Pandas** (2.2.3), **openpyxl** (3.1.5) | Data manipulation |
| Report Generation | **reportlab** (4.2.5) | Synthetic PDF generation |
| Retrieval | **rank-bm25** (0.2.2) | BM25 retrieval for RAG |
| HTTP Client | **httpx** (0.28.1) | Async HTTP for LLM calls |
| Testing | **pytest** (8.3.4) | Unit / integration tests |

### Frontend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | **React** 19 | UI library |
| Language | **TypeScript** 5.7 | Type-safe development |
| Build Tool | **Vite** 8.0.14 | Fast dev server + bundler |
| Styling | **Tailwind CSS** 4.1.17 | Utility-first CSS |
| Routing | **react-router-dom** 7.1.1 | Client-side routing |
| Icons | **lucide-react** | Icon library |
| Data Fetching | **@tanstack/react-query** 5.90.11 | Server state management |
| Charts | **recharts** 3.8.1 | Metrics visualization |
| Testing | **vitest** 4.1.7 | Unit testing |

### Database

- **PostgreSQL** (local instance required)
- **JSONB** columns for flexible schema storage of ML payloads
- Tables: `use_cases`, `raw_datasets`, `raw_artifacts`, `model_runs`, `processed_results`, `model_artifacts`, `audit_events`

### Infrastructure

- **Node.js** 24+ (for frontend build scripts and orchestration)
- **Python** 3.11+ (for backend and ML)
- **Virtual Environment** `.venv` (managed by `setup-backend.cjs`)
- **Concurrently** (for running backend + frontend together)

---

## The 10 Use Cases (Stages)

Each stage is a self-contained module under `backend/app/use_cases/<slug>/`. They share a common pattern:
- **Data Generation** (`data_generation.py`): Creates deterministic synthetic files under `data/<folder>/raw/`
- **Raw Data Loading** (`raw_data.py`): Loads files into Pydantic models
- **Service Layer** (`service.py`): Orchestrates the business logic, persists runs/results
- **Schema** (`schemas.py`): Pydantic models for API payloads
- **Startup Runner**: Triggered on backend startup via `ml_training_manager.py`
- **User Run**: Exposed via `POST /api/use-cases/{slug}/run` (or special endpoints like `chat`, `draft`, `research`, `orchestrate`)

### Stage 1: Fraud Detection

**Category**: Risk Operations  
**Adapter**: `autogluon-tabular`  
**Model Family**: Binary Classification  
**Primary Metric**: PR-AUC

**What it does**: Scores synthetic card and transfer transactions for fraud probability. Uses 27 engineered features (device, IP, merchant risk, velocity, authentication, geography, etc.).

**Data**:
- Train: 2,560 records
- Validation: 640 records
- Test: 800 records
- Total: 4,000 synthetic transactions

**Flow**:
1. Startup: Trains AutoGluon TabularPredictor on `train`, calibrates threshold on `val`, saves validation metrics.
2. User Action: Click **"Run Fraud Model"** to score the held-out `test` split.
3. UI: Shows PR-AUC, precision/recall, confusion matrix, ROC/PR curves, and a prediction table with risk levels (Low/Medium/High).

**Files**:
- `backend/app/use_cases/fraud_detection/training.py` — training logic
- `backend/app/use_cases/fraud_detection/threshold_tuning.py` — optimal threshold
- `backend/app/use_cases/fraud_detection/metrics.py` — evaluation metrics
- `backend/app/use_cases/fraud_detection/feature_engineering.py` — 27 features

### Stage 2: Credit Risk

**Category**: Lending  
**Adapter**: `autogluon-tabular`  
**Model Family**: Classification + Regression  
**Primary Metric**: ROC-AUC

**What it does**: Scores synthetic loan applications for 12-month default probability and recommended credit limit.

**Data**:
- Train: 1,920 applications
- Validation: 480 applications
- Test: 600 applications
- Total: 3,000 synthetic applications
- Fields: 23 applicant/underwriting fields + synthetic loss-given-default

**Flow**:
1. Startup: Trains on `train`, validates on `val`.
2. User Action: Click **"Run Credit Risk Model"** to score `test`.
3. UI: Shows ROC-AUC, PR-AUC, precision/recall, risk grades (A-E), and a decision table with recommended limits.

### Stage 3: Document OCR

**Category**: Document Intelligence  
**Adapter**: `ocr-local-gpt4o-fallback`  
**Model Family**: Document Extraction

**What it does**: Extracts structured data from synthetic banking documents (bank statements, account confirmations, income proofs, scanned PDFs, transfer notices).

**Data**:
- 12 customer packages (customer_0001 through customer_0012)
- 60 documents total: 36 digital PDFs, 12 scanned PDFs, 12 JPG transfer notices

**Flow**:
1. Startup: Runs deterministic extraction over all 60 documents.
   - `pdfplumber` / `PyMuPDF` for text-based PDFs.
   - `GPT-4o` fallback for scanned/image-only artifacts (when `OPENAI_API_KEY` is set).
2. User Action: Click **"Run Document OCR"** to rerun extraction.
3. UI: Document list by customer, field accuracy, table recall, confidence, and per-document field tables.

**Files**:
- `backend/app/use_cases/document_ocr/extraction.py` — OCR logic
- `backend/app/ai/ocr_adapter.py` — adapter interface

### Stage 4: Support Chatbot

**Category**: Customer Operations  
**Adapter**: `ollama-qwen-gpt4o-fallback`  
**Model Family**: RAG (Retrieval-Augmented Generation)

**What it does**: Answers internal support questions using a synthetic knowledge base of policies, procedures, FAQs, and product notices.

**Data**:
- 8 knowledge documents
- 26 deterministic BM25 chunks
- 8 evaluation questions

**Flow**:
1. Startup: Runs BM25 retrieval over the knowledge base and evaluates the 8 deterministic questions using Ollama Qwen (with GPT-4o fallback).
2. User Action:
   - **"Ask Support Chatbot"**: Type a custom question. The system retrieves relevant chunks and generates an answer with citations.
   - **"Run Support Evaluation"**: Re-runs the deterministic evaluation set.
3. UI: Answer card with source citations, retrieved chunk inspector, evaluation metrics (citation accuracy, source recall, average confidence).

**Files**:
- `backend/app/use_cases/support_chatbot/retrieval.py` — BM25 retrieval
- `backend/app/use_cases/support_chatbot/llm_service.py` — answer generation
- `backend/app/use_cases/support_chatbot/data_generation.py` — knowledge base

### Stage 5: Liquidity Forecast

**Category**: Treasury Operations  
**Adapter**: `autogluon-timeseries` (with deterministic baseline fallback)  
**Model Family**: Time Series

**What it does**: Forecasts synthetic branch and ATM cash demand with quantile outputs (p10, p50, p90), stockout risk, and replenishment recommendations.

**Data**:
- 6 branch/ATM series
- 180 history days
- 14 holdout forecast days
- Holiday/campaign calendars
- Cash inventory policy PDF

**Flow**:
1. Startup: Generates forecasts for the holdout period. Attempts AutoGluon TimeSeries; if unavailable, uses a deterministic local seasonal baseline.
2. User Action: Click **"Run Liquidity Forecast"** to rerun the held-out forecast.
3. UI: Forecast line chart (history + forecast), quantile bands, stockout risk, replenishment recommendations by location.

### Stage 6: AML Monitoring

**Category**: Compliance  
**Adapter**: `autogluon-tabular-local-llm-gpt4o-fallback`  
**Model Family**: Risk Scoring + Reporting

**What it does**: Prioritizes synthetic AML (Anti-Money Laundering) alerts and drafts suspicious activity narratives (SAR narratives).

**Data**:
- 2,500 synthetic alerts
- Transaction network sheets
- Entity relationships
- Suspicious activity notes
- Typology labels and SAR recommendation ground truth
- Train: 1,600 / Val: 400 / Test: 500

**Flow**:
1. Startup: Trains on `train`, calibrates on `val`, drafts top validation narratives.
2. User Action: Click **"Run AML Monitoring"** to score `test` and draft narratives for highest-risk alerts.
3. UI: Alert risk table, narrative drafts (summary, evidence bullets, recommended next steps), network summary, case note summaries.

**Primary Metric**: PR-AUC

### Stage 7: KYC/KYB

**Category**: Onboarding  
**Adapter**: `ocr-rules-autogluon-gpt4o-fallback`  
**Model Family**: Document + Risk Scoring

**What it does**: Verifies synthetic customer (KYC) and business (KYB) onboarding documents, applies deterministic policy rules, and flags manual-review cases.

**Data**:
- 48 onboarding packages (individual + business)
- 288 generated documents
- Sanctions and jurisdiction reference files
- Document policy rules
- Manual-review ground truth
- Train: 32 / Val: 8 / Test: 8

**Flow**:
1. Startup: Extracts documents, applies rules, trains on `train`, calibrates on `val`, scores `test`.
2. User Action: Click **"Run KYC/KYB Verification"** to score `test`.
3. UI: Package list with verification status (Approved/Needs Review/Rejected), risk scores, missing documents, field mismatches, rule findings.

**Primary Metric**: PR-AUC

### Stage 8: Email Automation

**Category**: Customer Communications  
**Adapter**: `template-rules-ollama-gpt4o-fallback`  
**Model Family**: Draft Generation + Compliance

**What it does**: Generates compliant synthetic customer email and notification drafts (service + campaign) with brand/tone guidelines and compliance checks.

**Data**:
- 120 synthetic customers
- 80 service events
- 40 campaign audience rows
- 24 evaluation cases
- Compliance policy PDFs, brand/tone guidelines
- No-send draft ground truth

**Flow**:
1. Startup: Runs evaluation over 24 cases, creates service and campaign drafts, applies deterministic compliance rules, persists provider/scoring details.
2. User Action:
   - **"Run Email Automation"**: Re-runs the evaluation set.
   - **Draft Workspace**: Creates one persisted synthetic draft at a time.
3. UI: Draft list with subject, body, compliance status, risk level, required disclosures, quality/compliance/personalization/readability scores.

**Important**: No real email sending is implemented. This is a draft-only system.

### Stage 9: Market Intelligence

**Category**: Research  
**Adapter**: `multi-agent-openai-web-search` (with deterministic synthetic fallback)  
**Model Family**: Agentic Research

**What it does**: Runs budget-controlled multi-agent market research with live web search (when configured) and produces cited banking impact briefs.

**Data**:
- 180 synthetic market articles
- 180 daily rate rows
- 80 competitor rate rows
- 36 economic calendar events
- 8 research brief cases
- Topic taxonomy
- Synthetic market snapshot PDF

**Flow**:
1. Startup: Runs a daily banking market brief. Uses OpenAI web search when `MARKET_LIVE_SEARCH_ENABLED=1` and API key is set; otherwise uses deterministic synthetic corpus.
2. User Action:
   - **"Run Market Brief"**: Re-runs the controlled brief.
   - **Research Workspace**: Performs one persisted scoped research run with clickable citations and budget counters.
3. UI: Brief headlines, top developments, banking implications, risks/opportunities, recommended actions, watchlist, source citations with URLs, agent trace (step-by-step), cost control (search call count, estimated cost).

### Stage 10: Workflow Orchestration

**Category**: Process Automation  
**Adapter**: `deterministic-dag-orchestrator-ollama-gpt4o-fallback`  
**Model Family**: Workflow Orchestration

**What it does**: Coordinates synthetic banking cases across persisted outputs from the first nine use cases. Executes deterministic workflow DAGs, applies routing/SLA rules, and may generate explanatory LLM summaries.

**Data**:
- 24 synthetic workflow cases
- 4 workflow types
- Case package PDFs/images/Excel/JSON files
- Dependency contracts
- SLA policy PDF
- Startup/held-out evaluation splits
- Deterministic routing ground truth

**Flow**:
1. Startup: Reads latest persisted outputs from the first nine use cases, executes deterministic workflow DAGs over startup cases, applies routing/SLA rules, generates LLM summaries.
2. User Action:
   - **"Run Workflow Batch"**: Scores held-out cases.
   - **Case Orchestration Workspace**: Persists one selected synthetic case.
3. UI: Case list with final status (Straight Through Approved / Needs Review / Escalated / Blocked / Rejected), risk levels, dependency status, SLA results, routing decisions, next best actions, case summaries.

**Important**: Does not retrain or rerun upstream models. It reads their latest persisted outputs.

---

## Data Directory

All synthetic raw files and database seed inputs live under `data/`. Folder names use `snake_case` (e.g., `fraud_detection`), while API slugs use `kebab-case` (e.g., `fraud-detection`).

### Layout

```
data/
  fraud_detection/
    raw/train/          # XLSX training files
    raw/val/            # XLSX validation files
    raw/test/           # XLSX test files

  credit_risk/
    raw/train/
    raw/val/
    raw/test/

  document_ocr/
    metadata.json
    ground_truth.json
    raw/customer_0001/
      bank_statement.pdf
      account_confirmation.pdf
      income_proof.pdf
      scanned_statement.pdf
      transfer_notice.jpg
    ... (customer_0001 through customer_0012)

  support_chatbot/
    metadata.json
    ground_truth.json
    raw/policies/       # PDFs
    raw/procedures/     # Markdown
    raw/faq/            # JSON
    raw/notices/        # TXT
    raw/evaluation/     # JSON

  liquidity_forecast/
    metadata.json
    ground_truth.json
    raw/timeseries/     # Excel
    raw/calendar/       # CSV
    raw/policies/       # PDF

  aml_monitoring/
    raw/train/          # Excel
    raw/val/            # Excel
    raw/test/           # Excel
    raw/network/        # Excel
    raw/entities/       # JSON
    raw/case_notes/     # PDF
    metadata.json
    ground_truth.json

  kyc_kyb/
    raw/individual/     # Packages
    raw/business/       # Packages
    raw/watchlists/     # Reference files
    raw/policies/       # PDF
    metadata.json
    ground_truth.json

  email_automation/
    raw/customers/      # JSON
    raw/events/         # JSON
    raw/campaigns/      # Excel
    raw/templates/      # Markdown
    raw/policies/       # PDF
    raw/evaluation/     # JSON
    metadata.json
    ground_truth.json

  market_intelligence/
    raw/news/           # JSON
    raw/rates/          # CSV
    raw/competitors/    # Excel
    raw/calendar/       # CSV
    raw/snapshot/       # PDF
    raw/taxonomy/       # JSON
    raw/evaluation/     # JSON
    metadata.json
    ground_truth.json

  workflow_orchestration/
    raw/cases/          # Case packages
    raw/definitions/    # JSON
    raw/contracts/      # Dependency contracts
    raw/policies/       # PDF (SLA)
    raw/evaluation/     # JSON
    metadata.json
    ground_truth.json
```

### Commands

```powershell
# Generate all synthetic raw data (deterministic, seeded)
npm run data:generate

# Seed raw artifacts into PostgreSQL
npm run db:seed
```

Generated XLSX, PDF, JPG, Markdown, TXT, and JSON raw files are `.gitignore`'d; run `data:generate` after clone.

---

## Database Schema

Managed via **SQLModel** with **PostgreSQL** backend. JSONB is used for flexible ML payloads.

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `use_cases` | Registry of 10 stages | `slug` (PK), `title`, `category`, `status`, `implementation_order` |
| `raw_datasets` | Seed metadata previews | `id`, `use_case_slug`, `dataset_key`, `source_type`, `payload` (JSONB) |
| `raw_artifacts` | File pointers | `id`, `use_case_slug`, `file_name`, `file_path`, `artifact_type`, `metadata_json` (JSONB) |
| `model_runs` | Every run (training + user) | `id`, `use_case_slug`, `adapter_type`, `provider_used`, `model_name`, `status`, `duration_ms`, `metrics` (JSONB) |
| `processed_results` | ML outputs | `id`, `run_id`, `use_case_slug`, `result_type`, `payload` (JSONB), `explanation` (JSONB) |
| `model_artifacts` | Trained model paths | `id`, `use_case_slug`, `artifact_type`, `local_path`, `metadata_json` (JSONB) |
| `audit_events` | Audit trail | `id`, `actor`, `action`, `entity_type`, `entity_id`, `metadata_json` (JSONB) |

### Relationships

- `model_runs` → `processed_results` (one-to-many)
- `use_cases` → `raw_datasets`, `raw_artifacts`, `model_runs`, `processed_results` (one-to-many)
- `model_runs` → `model_artifacts` (one-to-many)

---

## API Endpoint Map

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Database connectivity check |
| `/api/ready` | GET | API is up; ML may still be running |
| `/api/ml-ready` | GET | All startup processing complete |
| `/api/startup/status` | GET | Full startup pipeline status (all 10 stages) |
| `/api/ai/health` | GET | Adapter readiness (AutoGluon, OCR, Ollama, OpenAI, WebSearch) |

### Use Cases

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/use-cases` | GET | List all 10 use cases with latest run + artifact counts |
| `/api/use-cases/{slug}` | GET | Use case metadata |
| `/api/use-cases/{slug}/raw` | GET | Raw datasets + artifacts for this use case |
| `/api/use-cases/{slug}/training-status` | GET | Startup training status for this use case |
| `/api/use-cases/{slug}/evaluations` | GET | Latest evaluation bundle (val + test) |
| `/api/use-cases/{slug}/run` | POST | Trigger a user run (e.g., "Run Fraud Model") |
| `/api/use-cases/{slug}/runs` | GET | List all runs for this use case |
| `/api/use-cases/{slug}/runs/{run_id}` | GET | Run detail + results |
| `/api/use-cases/{slug}/runs/{run_id}/progress` | GET | Real-time progress (percent + stage) |
| `/api/use-cases/{slug}/runs/{run_id}/result` | GET | Final result payload |

### Special Actions (per use case)

| Endpoint | Method | Use Case | Description |
|----------|--------|----------|-------------|
| `/api/use-cases/support-chatbot/chat` | POST | Support Chatbot | Ask a custom question |
| `/api/use-cases/email-automation/draft` | POST | Email Automation | Create a single draft |
| `/api/use-cases/market-intelligence/research` | POST | Market Intelligence | Run scoped research |
| `/api/use-cases/workflow-orchestration/orchestrate` | POST | Workflow Orchestration | Orchestrate a single case |

### Authentication

Currently **no authentication** is implemented. This is a local demonstration system.

---

## AI Adapters & Model Infrastructure

All AI backends are abstracted behind adapter classes in `backend/app/ai/`.

### AutoGluon Tabular Adapter

- **File**: `backend/app/ai/autogluon_adapter.py`
- **Purpose**: Binary classification for Fraud Detection, Credit Risk, AML Monitoring, KYC/KYB
- **Backend**: AutoGluon `TabularPredictor` with LightGBM, XGBoost, CatBoost
- **Health Check**: Verifies if AutoGluon is installed and a model directory exists
- **Lock**: AutoGluon fit operations share a local threading lock to prevent Ray worker contention

### AutoGluon TimeSeries Adapter

- **File**: `backend/app/ai/autogluon_timeseries_adapter.py`
- **Purpose**: Liquidity Forecast
- **Backend**: AutoGluon `TimeSeriesPredictor`
- **Fallback**: If AutoGluon is unavailable, the system uses a deterministic local seasonal baseline

### Local OCR Adapter

- **File**: `backend/app/ai/ocr_adapter.py`
- **Purpose**: Document OCR
- **Backends**: `pdfplumber` + `PyMuPDF` for text-based PDFs
- **Fallback**: `GPT-4o` (OpenAI) for scanned/image-only artifacts when configured
- **Health Check**: Verifies `pdfplumber` and `PyMuPDF` are installed

### Ollama Qwen Adapter

- **File**: `backend/app/ai/ollama_qwen_adapter.py`
- **Purpose**: Support Chatbot, Email Automation, Workflow Orchestration LLM summaries
- **Model**: `qwen2.5:7b` (or as configured in `.env`)
- **Endpoint**: `http://localhost:11434` (Ollama)
- **Timeout**: `LOCAL_MODEL_TIMEOUT_SECONDS` (default 30s)
- **Fallback**: `GPT-4o` if Ollama is unavailable or times out

### OpenAI GPT-4o Adapter

- **File**: `backend/app/ai/openai_gpt4o_adapter.py`
- **Purpose**: Universal fallback for OCR, Chatbot, Email, Workflow, AML narratives, KYC extraction
- **Model**: `gpt-4o` (or as configured in `.env`)
- **Requirement**: `OPENAI_API_KEY` in `.env`

### Web Search Adapter

- **File**: `backend/app/ai/web_search_adapter.py`
- **Purpose**: Market Intelligence live search
- **Models**: `gpt-5.4-mini` (research), `gpt-5-search-api` (fallback)
- **Budget Control**: Max search calls per run type (startup, user, deep) are configurable in `.env`

---

## Prerequisites

### Required

1. **Node.js** 24+ (Check with `node -v`)
2. **Python** 3.11+ (Check with `python --version`)
3. **PostgreSQL** running locally (outside the app)
   - Default: `localhost:5432`
   - User: `postgres`
   - Password: `admin123` (or as configured)
   - Database: `banking_ai` (must be created beforehand)

### Optional

4. **Ollama** (for local LLM inference)
   - Install from [ollama.com](https://ollama.com)
   - Pull the model: `ollama pull qwen2.5:7b`
   - Ensure Ollama is running: `ollama serve` (or system service)
   - Endpoint: `http://localhost:11434`

5. **OpenAI API Key** (for cloud fallbacks and Market Intelligence live search)
   - Get from [platform.openai.com](https://platform.openai.com)
   - Set in `.env` as `OPENAI_API_KEY=sk-...`

6. **AutoGluon** (will be installed automatically by `npm run setup:backend`)
   - Requires ~2-4 GB RAM for training with default settings
   - For faster startup, reduce `AUTOGLUON_TIME_LIMIT_SECONDS` and `AUTOGLUON_NUM_BAG_FOLDS`

### Windows Notes

- If you encounter `WinError 10048` (port already in use), run `npm run dev:stop` before starting.
- `npm run dev:full` automatically frees ports 8001 and 5173 before starting.

---

## Setup Guide

### Step 1: Clone & Install Node Dependencies

```powershell
# Install root + frontend dependencies
npm install
npm run setup:frontend
```

### Step 2: Create Python Virtual Environment

```powershell
# Creates .venv at project root, installs requirements.txt
npm run setup:backend
```

This creates a `.venv` and installs:
- `requirements.txt` (FastAPI, SQLModel, Pandas, OCR libs, etc.)
- `requirements.txt` also includes ML deps (AutoGluon, Ray, OpenAI, CatBoost)

### Step 3: Configure Environment Variables

```powershell
copy .env.example .env
```

Edit `.env` to set your `DATABASE_URL` and optionally `OPENAI_API_KEY`:

```env
DATABASE_URL=postgresql+psycopg://postgres:admin123@localhost:5432/banking_ai
OPENAI_API_KEY=sk-your-key-here
```

Ensure PostgreSQL is running and the `banking_ai` database exists.

### Step 4: Create Database & Migrate

```powershell
npm run db:migrate
```

This creates all tables (`use_cases`, `raw_datasets`, `model_runs`, etc.).

### Step 5: Generate Synthetic Data

```powershell
npm run data:generate
```

This writes deterministic XLSX, PDF, JPG, JSON, Markdown, and TXT files under `data/`.

### Step 6: Seed Database

```powershell
npm run db:seed
```

This loads raw dataset metadata and artifact records into PostgreSQL.

### Step 7: Check AI Adapter Health

```powershell
npm run ai:check
```

This runs a Python script that checks if AutoGluon, OCR, Ollama, OpenAI, and WebSearch are available. If an adapter is missing, you'll see a setup hint.

---

## Running the Application

### Full Stack (Recommended)

```powershell
npm run dev:full
# or alias:
npm run full
```

This:
1. Frees ports 8001 and 5173 (kills stale processes).
2. Starts the backend (`uvicorn` on port 8001).
3. Waits for `http://127.0.0.1:8001/api/ready` (database reachable + API accepting traffic).
4. Starts the frontend (`vite` on port 5173).

**Access**:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8001
- API Docs (Swagger UI): http://localhost:8001/docs

### Backend Only

```powershell
npm run dev:backend
```

### Frontend Only

```powershell
npm run dev:frontend
```

### Stop All Dev Processes

```powershell
npm run dev:stop
```

This kills any processes using ports 8001 and 5173.

### Startup Pipeline

When the backend starts (via `dev:full` or `dev:backend`), the following happens automatically:

1. **Reset**: All prior processed outputs for the 10 use cases are cleared from the database.
2. **Sequential Training**: 10 stages run in order:
   - Fraud Detection (training)
   - Credit Risk (training)
   - Document OCR (extraction)
   - Support Chatbot (evaluation)
   - Liquidity Forecast (forecast generation)
   - AML Monitoring (training + narratives)
   - KYC/KYB (extraction + training)
   - Email Automation (evaluation)
   - Market Intelligence (brief generation)
   - Workflow Orchestration (DAG execution)
3. **Progress**: The frontend shows a **Startup Training Strip** at the top with a progress bar and per-stage status badges.
4. **API Ready**: The API is available immediately, but ML endpoints may return `409` (startup not complete) until the relevant stage finishes.

**Poll endpoints**:
- `GET /api/ready` — API + database status
- `GET /api/ml-ready` — All startup stages complete
- `GET /api/startup/status` — Full pipeline state (all 10 stages)
- `GET /api/use-cases/{slug}/training-status` — Per-stage status

---

## Startup Pipeline & ML Training

### Queue Design

The backend uses **two FIFO queues** (`backend/app/services/ml_job_queue.py`):

1. **Startup Queue**: Runs the 10-stage pipeline sequentially on backend startup.
2. **User Run Queue**: Runs user-triggered jobs (e.g., clicking "Run Fraud Model") after the corresponding startup stage completes.

This ensures:
- Startup jobs never compete with each other.
- User runs can start while later startup stages are still running.
- AutoGluon fit operations share a **local lock** so they don't compete for Ray workers and RAM.

### Stage States

Each stage can be in one of these states:
- `idle` — Not started
- `queued` — Waiting for previous stage
- `running` — Currently processing
- `completed` — Finished successfully
- `failed` — Error occurred
- `skipped` — Skipped via `SKIP_STARTUP_TRAINING=1`

### Skipping / Forcing Training

You can control startup behavior via `.env`:

```env
SKIP_STARTUP_TRAINING=1    # Skip all startup ML (useful for frontend dev)
FORCE_RETRAIN=1            # Force retraining even if a model exists
```

Alternatively, set environment variables before running:

```powershell
$env:SKIP_STARTUP_TRAINING="1"
npm run dev:full
```

### Retraining a Specific Model

If you change data files or want to retrain a specific model:

```powershell
# Delete the model directory
Remove-Item -Recurse -Force backend/models/fraud-detection/autogluon
# Restart backend
npm run dev:full
```

The backend will detect the missing model and retrain on startup.

### AutoGluon Configuration

For **local development**, the default `.env` values keep startup practical:

```env
AUTOGLUON_TIME_LIMIT_SECONDS=180
AUTOGLUON_NUM_BAG_FOLDS=0
AUTOGLUON_NUM_CPUS=1
```

For **higher quality** (slower) retraining:

```env
AUTOGLUON_TIME_LIMIT_SECONDS=600
AUTOGLUON_NUM_BAG_FOLDS=5
AUTOGLUON_NUM_CPUS=4
```

---

## Environment Variables

All configuration is managed via `.env` (read by `backend/app/config.py` using Pydantic Settings).

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/banking_ai` | PostgreSQL connection string |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key (required for GPT-4o fallback and Market Intelligence) |
| `OPENAI_MODEL` | `gpt-4o` | Default OpenAI model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server endpoint |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Local LLM model name |
| `LOCAL_MODEL_TIMEOUT_SECONDS` | `30` | Timeout for Ollama requests |
| `AUTOGLUON_PRESET` | `good_quality` | AutoGluon quality preset (`medium`, `good_quality`, `best`, `optimize_for_deployment`) |
| `AUTOGLUON_TIME_LIMIT_SECONDS` | `180` | Max training time per AutoGluon fit |
| `AUTOGLUON_NUM_BAG_FOLDS` | `0` | Number of bag folds (0 = disabled for speed) |
| `AUTOGLUON_NUM_CPUS` | `1` | CPUs for AutoGluon/Ray |
| `SKIP_STARTUP_TRAINING` | `0` | Set to `1` to skip all startup ML |
| `FORCE_RETRAIN` | `0` | Set to `1` to force retraining |
| `MARKET_LIVE_SEARCH_ENABLED` | `1` | Enable live web search for Market Intelligence |
| `MARKET_RESEARCH_MODEL` | `gpt-5.4-mini` | Primary model for market research |
| `MARKET_SEARCH_FALLBACK_MODEL` | `gpt-5-search-api` | Fallback model for web search |
| `MARKET_SEARCH_CONTEXT_SIZE` | `low` | Search context size (`low`, `medium`, `high`) |
| `MARKET_MAX_SEARCH_CALLS_STARTUP` | `6` | Max live search calls during startup brief |
| `MARKET_MAX_SEARCH_CALLS_USER_RUN` | `10` | Max live search calls during user "Run Market Brief" |
| `MARKET_MAX_SEARCH_CALLS_DEEP` | `16` | Max live search calls during deep research |
| `MARKET_SEARCH_TIMEOUT_SECONDS` | `45` | Timeout for each search call |

---

## Frontend Structure

```
frontend/src/
  App.tsx              # Main layout (sidebar + routes + startup strip)
  api.ts               # API client (TanStack Query wrappers + types)
  useCases.ts          # Static use case registry (10 items)
  startupTraining.ts   # Startup status polling hooks
  fraudPredictionQuality.ts  # Fraud score classification helpers
  main.tsx             # React entry point (React 19)
  styles.css           # Tailwind imports
  vite-env.d.ts       # Vite env types
```

### Layout

- **Sidebar** (fixed, 72 width): Logo + navigation links for all 10 use cases. Each link shows a status badge (`Live` or `Stage N`).
- **Startup Training Strip** (conditional): Appears when startup is active. Shows active stage title, progress bar, and grid of all 10 stage statuses (completed = green, running = amber, failed = red).
- **Dashboard** (`/`): Overview cards (Use Case count, Implemented count, Raw Artifacts, Startup Stage, GPT-4o Fallbacks). Includes a "Use Case Roadmap" panel and "Adapter Readiness" panel.
- **Use Case Pages** (`/use-cases/:slug`): Each use case has a dedicated page with:
  - Metric cards (record counts, statuses, provider used)
  - Raw Artifacts panel
  - Run / Chat / Draft / Research / Orchestrate panel
  - Evaluation panels (charts, tables, narratives)
  - Run History panel

### State Management

- **TanStack React Query** handles all server state:
  - `useQuery` for fetching data (use cases, raw artifacts, evaluations, runs, adapter health)
  - `useMutation` for actions (run, chat, draft, research, orchestrate)
  - `refetchInterval` for polling progress during active runs

---

## Development & Testing

### Full Test Suite

```powershell
npm run test:full
```

Runs backend `pytest` + frontend `vitest` sequentially.

### Backend Tests Only

```powershell
npm --prefix backend run test
# or
npm run test:full  # (runs both)
```

### Frontend Tests Only

```powershell
npm --prefix frontend run test
```

### Lint / Type Check

The frontend uses TypeScript (`tsc -b`) as part of the build:

```powershell
npm --prefix frontend run build
```

### Preview Production Build

```powershell
npm --prefix frontend run preview
```

Serves the built frontend on `http://localhost:4173`.

### Adding a New Use Case (Advanced)

If you want to extend the portal with an 11th stage:

1. Add entry to `backend/app/use_cases/registry.py`.
2. Create folder `backend/app/use_cases/<new_slug>/` with `data_generation.py`, `raw_data.py`, `schemas.py`, `service.py`.
3. Add entry to `frontend/src/useCases.ts`.
4. Add page component to `frontend/src/App.tsx` in `UseCasePage`.
5. Add API types to `frontend/src/api.ts`.
6. Add `data/<new_slug>/` folder and `data_generation.py` integration.
7. Register startup runner in `backend/app/services/ml_training_manager.py`.
8. Add routes to `backend/app/api/use_cases.py`.

---

## Troubleshooting

### Port Already in Use (WinError 10048)

**Symptom**: `Error: listen EADDRINUSE: address already in use :::8001` or `WinError 10048`

**Fix**:
```powershell
npm run dev:stop
# Then restart
npm run dev:full
```

Or manually kill the process:
```powershell
# Windows
netstat -ano | findstr :8001
# Note the PID, then
taskkill /PID <PID> /F
```

### AutoGluon Not Found

**Symptom**: `AutoGluonTabularAdapter` health check shows "not installed" or `ModuleNotFoundError: No module named 'autogluon'`

**Fix**:
```powershell
npm run setup:backend
```

If it still fails, try installing manually:
```powershell
.venv\Scripts\python.exe -m pip install autogluon.tabular[lightgbm,xgboost]==1.5.0 autogluon.timeseries==1.5.0
```

### PostgreSQL Connection Failed

**Symptom**: `psycopg.OperationalError: connection failed`

**Fix**:
1. Ensure PostgreSQL service is running.
2. Check that the `banking_ai` database exists:
   ```powershell
   psql -U postgres -c "CREATE DATABASE banking_ai;"
   ```
3. Verify `.env` `DATABASE_URL` matches your PostgreSQL credentials.
4. Check if the port is correct (default 5432).

### Ollama Timeout

**Symptom**: `OllamaQwenAdapter` shows "timeout" or "unreachable"

**Fix**:
1. Ensure Ollama is running: `ollama serve` or start the system service.
2. Pull the model: `ollama pull qwen2.5:7b`
3. Increase timeout in `.env`: `LOCAL_MODEL_TIMEOUT_SECONDS=60`
4. If Ollama is unavailable, the system will automatically fall back to `GPT-4o` (if `OPENAI_API_KEY` is set).

### Frontend Won't Start

**Symptom**: `Failed to connect to localhost:8001` or blank page

**Fix**:
1. Ensure backend is running first (`npm run dev:backend` in a separate terminal).
2. Wait for `/api/ready` to return `200` (the `wait-for-backend.cjs` script does this automatically in `dev:full`).
3. Check browser console for CORS errors. The backend already allows `http://localhost:5173`.

### Slow Startup Training

**Symptom**: Startup takes 10+ minutes

**Fix**:
- Reduce AutoGluon time limit in `.env`:
  ```env
  AUTOGLUON_TIME_LIMIT_SECONDS=60
  AUTOGLUON_NUM_BAG_FOLDS=0
  AUTOGLUON_NUM_CPUS=1
  ```
- Or skip startup training entirely:
  ```env
  SKIP_STARTUP_TRAINING=1
  ```

### Model Not Updating After Data Change

**Fix**:
```powershell
Remove-Item -Recurse -Force backend/models/<use-case>/autogluon
npm run dev:full
```

---

## Tips & Best Practices

### For Demonstrations

- Use `AUTOGLUON_TIME_LIMIT_SECONDS=60` and `AUTOGLUON_NUM_BAG_FOLDS=0` for fast demos.
- Set `SKIP_STARTUP_TRAINING=1` if you only want to show the frontend and static data.
- Ensure `OPENAI_API_KEY` is set for the best experience (GPT-4o fallback improves OCR, chatbot, and market intelligence).

### For Development

- Run `npm run dev:backend` in one terminal and `npm run dev:frontend` in another for faster debugging.
- Use `npm run ai:check` after any environment change to verify adapter health.
- Use the Swagger UI (`http://localhost:8001/docs`) to test API endpoints directly.

### For Production (Not Recommended)

This is a **local demonstration MVP**. It is not designed for production deployment without:
- Adding authentication/authorization
- Hardening the API (rate limiting, input validation)
- Using a production WSGI/ASGI server (e.g., Gunicorn behind Nginx)
- Securing the database connection (SSL, restricted user)
- Removing synthetic data and connecting to real banking systems

### Data Reproducibility

All synthetic data is generated deterministically. If you delete `data/` and re-run:
```powershell
npm run data:generate
npm run db:seed
```
You will get the exact same files and database contents (assuming the same generator version).

---

## Project Structure Summary

```
banking_ai/
  .env                  # Environment variables (copy from .env.example)
  .env.example          # Template
  .venv/                # Python virtual environment (created by setup)
  README.md             # This file
  package.json          # Root npm scripts (orchestrates frontend + backend)
  requirements.txt      # Core Python dependencies (FastAPI, SQLModel, Pandas, etc.)
  requirements.txt      # All Python dependencies (FastAPI + ML)
  
  backend/
    app/
      main.py           # FastAPI entry point + lifespan (startup pipeline)
      config.py         # Pydantic Settings (.env reader)
      data_paths.py     # Path helpers for data/ and models/
      
      api/
        health.py       # /api/health, /api/ready, /api/ai/health, /api/startup/status
        use_cases.py    # All /api/use-cases/* routes
      
      db/
        models.py       # SQLModel tables (7 core tables)
        session.py      # Database session factory
      
      services/
        ml_training_manager.py   # Orchestrates 10-stage startup pipeline
        ml_job_queue.py          # FIFO queues (startup + user)
        run_cleanup.py           # Resets outputs before training
        run_progress.py          # Progress tracking helpers
        seeding.py               # Database seeding logic
      
      ai/
        autogluon_adapter.py          # AutoGluon Tabular
        autogluon_timeseries_adapter.py # AutoGluon TimeSeries
        autogluon_runtime.py          # Runtime patches
        ocr_adapter.py                # Local OCR + GPT-4o fallback
        ollama_qwen_adapter.py        # Local LLM
        openai_gpt4o_adapter.py       # Cloud LLM
        web_search_adapter.py         # Market Intelligence web search
      
      use_cases/
        registry.py            # Static registry of 10 use cases
        fraud_detection/       # Training, metrics, threshold tuning, feature engineering
        credit_risk/           # Training, metrics, risk scoring
        document_ocr/          # Extraction, OCR service
        support_chatbot/       # BM25 retrieval, LLM answer generation
        liquidity_forecast/    # TimeSeries forecasting, baseline fallback
        aml_monitoring/        # Training, narrative generation, network analysis
        kyc_kyb/               # Document extraction, rule engine, risk scoring
        email_automation/      # Template engine, compliance rules, scoring
        market_intelligence/   # Multi-agent research, web search, signal scoring
        workflow_orchestration/ # DAG engine, dependency loader, routing, SLA
      
      scripts/
        generate_data.py     # npm run data:generate
        migrate.py           # npm run db:migrate
        seed.py              # npm run db:seed
        ai_check.py          # npm run ai:check
    
    models/                # Trained AI models (AutoGluon artifacts)
    preview_banking_ai.db  # SQLite preview (not primary DB) — moved to .agent_test/
  
  frontend/
    src/
      App.tsx              # Main application (sidebar + routing)
      api.ts               # API client + TypeScript interfaces
      useCases.ts          # Static use case list
      startupTraining.ts   # Startup polling hooks
      fraudPredictionQuality.ts  # Score classification
      main.tsx             # React entry
      styles.css           # Tailwind
      vite-env.d.ts        # Vite types
    index.html             # HTML entry
    vite.config.ts         # Vite configuration
    tsconfig.json          # TypeScript config
  
  data/                  # Synthetic raw data (generated, gitignored)
    fraud_detection/
    credit_risk/
    document_ocr/
    support_chatbot/
    liquidity_forecast/
    aml_monitoring/
    kyc_kyb/
    email_automation/
    market_intelligence/
    workflow_orchestration/
  
  storage/               # Trained models, logs, screenshots
    models/
      fraud-detection/
      credit-risk/
      ...
    *.log                # Dev logs
  
  scripts/               # Node.js orchestration scripts
    setup-backend.cjs    # Creates .venv + installs Python deps
    python.cjs           # Runs .venv Python (cross-platform)
    wait-for-backend.cjs # Waits for /api/ready before starting frontend
    free-dev-ports.cjs   # Kills stale processes on ports 8001/5173
```

---

## License

This is a private/local demonstration project. All data is synthetic and does not contain real customer information.

---

**Happy exploring the Banking AI Portal!** If you have questions, check the `backend/app/use_cases/<slug>/` directories for the implementation details of each stage.
