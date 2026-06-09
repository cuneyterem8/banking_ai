# CONTEXT.md - Banking AI Portal

> **AI INSTRUCTION**: Every new session MUST read this file first before any action. This is the single source of truth for project context.

## Project Identity

- **Name**: Banking AI Portal
- **Type**: Local-first staged MVP for 10 banking AI use cases
- **Language**: All app-facing text, source comments, schemas, and synthetic sample content are in English
- **Current Status**: All 10 stages implemented (Stage 1-10 Live)
- **Last Updated**: 2026-06-09 (models moved to backend/, storage/ removed)

## Quick Overview

A demonstration system showing how modern AI/ML can be applied to banking operations. Uses deterministic synthetic data, persists all artifacts to PostgreSQL, and provides a React dashboard for interacting with each use case.

### Key Design Principles
- **Local-first**: Everything runs on your machine (no cloud dependencies except optional OpenAI)
- **Staged MVP**: Each of 10 use cases is a discrete stage with own data, models, and UI
- **Modular Adapters**: AI backends abstracted behind adapters (AutoGluon, Ollama, OpenAI, Local OCR)
- **Deterministic Data**: Synthetic datasets generated via seeded scripts for reproducible results
- **PostgreSQL Persistence**: All runs, results, raw artifacts, and evaluations stored in database
- **Queue-based Concurrency**: Heavy ML jobs use sequential startup queue + separate user-run queue

## Technology Stack

### Backend (Python)
- **FastAPI** 0.115.6 (web framework)
- **Uvicorn** 0.34.0 (ASGI server)
- **SQLModel** 0.0.22 (ORM + Pydantic)
- **psycopg** 3.2.3 (PostgreSQL driver)
- **Pydantic Settings** 2.7.1 (.env configuration)
- **Pandas** 2.2.3, **openpyxl** 3.1.5 (data processing)
- **ReportLab** 4.2.5, **Pillow** 11.1.0 (PDF/image generation)
- **pdfplumber** 0.11.9, **PyMuPDF** 1.27.2.3, **pypdf** 6.12.2 (OCR)
- **rank-bm25** 0.2.2 (RAG retrieval)
- **httpx** 0.28.1 (HTTP client)
- **pytest** 8.3.4 (testing)

### ML/AI Stack
- **AutoGluon** 1.5.0 (tabular + timeseries)
- **Ray** 2.52.1 (distributed backend)
- **LightGBM, XGBoost, CatBoost** (ensemble)
- **Ollama** (local LLM, qwen2.5:7b)
- **OpenAI** (gpt-4o, gpt-5.4-mini, gpt-5-search-api)

### Frontend (React + TypeScript)
- **React** 19 (UI library)
- **TypeScript** 5.7
- **Vite** 8.0.14 (build tool)
- **Tailwind CSS** 4.1.17 (styling)
- **react-router-dom** 7.1.1 (routing)
- **lucide-react** (icons)
- **@tanstack/react-query** 5.90.11 (data fetching)
- **recharts** 3.8.1 (charts)
- **vitest** 4.1.7 (testing)

### Database
- **PostgreSQL** with JSONB columns for flexible ML payloads
- 7 core tables: use_cases, raw_datasets, raw_artifacts, model_runs, processed_results, model_artifacts, audit_events

### Infrastructure
- **Node.js** 24+ (frontend build + orchestration)
- **Python** 3.11+ (backend + ML)
- **Virtual Environment** `.venv` (managed by setup-backend.cjs)
- **Concurrently** (running backend + frontend together)

## Architecture Summary

```
Frontend (React) http://localhost:5173
    |
    | REST API (CORS)
    v
Backend (FastAPI) http://localhost:8001
    |
    |-- API Layer (/api/health, /api/use-cases, /api/use-cases/{slug}/run, etc.)
    |-- Services Layer (ML Training Manager, ML Job Queue, Run Cleanup, Progress Tracking)
    |-- Use Case Layer (10 modules: fraud_detection, credit_risk, document_ocr, support_chatbot, liquidity_forecast, aml_monitoring, kyc_kyb, email_automation, market_intelligence, workflow_orchestration)
    |-- AI Adapter Layer (AutoGluon, OCR, Ollama, OpenAI, WebSearch)
    |-- Data/Storage Layer (PostgreSQL, data/ raw files, backend/models/)
```

### Communication Flow
1. Frontend makes REST API calls to backend
2. Backend serves FastAPI endpoints, triggers background ML pipeline on startup
3. ML Pipeline runs 10 stages sequentially: Fraud -> Credit -> OCR -> Chatbot -> Liquidity -> AML -> KYC -> Email -> Market -> Workflow
4. User runs (clicking "Run" buttons) go to separate user-run queue
5. AutoGluon models share a local lock to prevent Ray/RAM contention
6. All results persisted to PostgreSQL via SQLModel

## Current State (2026-06-09)

### Implemented
- All 10 stages are live and functional
- Backend startup pipeline runs sequentially (10 stages)
- Frontend dashboard with sidebar navigation, startup training strip, adapter health panel
- Full data generation pipeline (deterministic synthetic data)
- Database migration and seeding scripts
- AI adapter health check system
- Port management (free-dev-ports.cjs)

### Active Models
- **Fraud Detection**: AutoGluon Tabular, PR-AUC metric, 2560/640/800 train/val/test
- **Credit Risk**: AutoGluon Tabular, ROC-AUC metric, 1920/480/600 train/val/test
- **Document OCR**: pdfplumber + PyMuPDF + GPT-4o fallback, 12 customer packages, 60 documents
- **Support Chatbot**: BM25 + Ollama Qwen + GPT-4o fallback, 8 docs, 26 chunks, 8 eval questions
- **Liquidity Forecast**: AutoGluon TimeSeries + baseline fallback, 6 series, 180 history days
- **AML Monitoring**: AutoGluon + local LLM + GPT-4o, 2500 alerts, PR-AUC metric
- **KYC/KYB**: OCR + rules + AutoGluon + GPT-4o, 48 packages, PR-AUC metric
- **Email Automation**: Templates + rules + Ollama + GPT-4o, 120 customers, 24 eval cases
- **Market Intelligence**: Multi-agent + OpenAI web search, 180 articles, live search
- **Workflow Orchestration**: Deterministic DAG + Ollama + GPT-4o, 24 cases, reads upstream outputs

### Development Environment
- Working directory: `C:\Users\cnytC\Desktop\code_projects\banking_ai`
- Git repo: Yes
- Platform: Windows (win32)
- Node.js: 24+
- Python: 3.11+
- PostgreSQL: Local (localhost:5432)
- Ollama: Optional (localhost:11434)
- OpenAI API: Optional (configured in .env)
- AI Context: `.context/` (AGENTS.md, CONTEXT.md, STAGES.md, HISTORY.md, PROMPT.md)
- AI Workspace: `.agent_test/` (temporary test/draft files, gitignored)

### Active TODOs

#### High Priority
- [ ] Review and optimize all 10 stage startup times (currently ~5-10 minutes total)
- [ ] Add comprehensive error handling for adapter fallbacks (when Ollama is down, GPT-4o fails)
- [ ] Implement caching layer for repeated ML predictions (reduce re-computation)
- [ ] Add frontend tests for all 10 use case pages (currently only App.tsx has tests)

#### Medium Priority
- [ ] Add pagination for large dataset tables (fraud/credit risk prediction tables)
- [ ] Implement dark/light mode toggle (currently only dark mode)
- [ ] Add export functionality for predictions (CSV/Excel download)
- [ ] Create mobile-responsive layout (currently desktop-only)
- [ ] Add real-time notifications for ML pipeline completion

#### Low Priority
- [ ] Add i18n support for Turkish language (user is Turkish)
- [ ] Create Docker compose for easier setup
- [ ] Add rate limiting for API endpoints
- [ ] Implement user authentication system
- [ ] Add Prometheus metrics for monitoring

## File Structure (Key Files)

### Root Level
- `package.json` - Root npm scripts (dev:full, setup, data:generate, db:migrate, db:seed, ai:check)
- `.env` / `.env.example` - Environment variables
- `.venv/` - Python virtual environment
- `requirements.txt` - All Python deps (FastAPI, SQLModel, Pandas, OCR libs, AutoGluon, Ray, OpenAI, CatBoost)
- `README.md` - Comprehensive project documentation
- `.context/CONTEXT.md` - This file (AI context)
- `.context/STAGES.md` - 10 stage details
- `.context/HISTORY.md` - Session history
- `.context/AGENTS.md` - AI instructions
- `.agent_test/` - AI workspace for temporary test/draft files
  - `backend_tests/` - Python backend tests (pytest)
  - `frontend_tests/` - TypeScript frontend tests (vitest)
  - `screenshots/` - UI test screenshots
  - `*.log` - Runtime/test logs

### Backend (`backend/`)
- `app/main.py` - FastAPI entry point + lifespan (startup pipeline)
- `app/config.py` - Pydantic Settings (.env reader)
- `app/data_paths.py` - Path helpers for data/ and models/
- `app/api/health.py` - /api/health, /api/ready, /api/ai/health, /api/startup/status
- `app/api/use_cases.py` - All /api/use-cases/* routes
- `app/db/models.py` - SQLModel tables (7 tables)
- `app/db/session.py` - Database session factory
- `app/services/ml_training_manager.py` - 10-stage startup pipeline orchestrator
- `app/services/ml_job_queue.py` - FIFO queues (startup + user)
- `app/services/run_cleanup.py` - Resets outputs before training
- `app/services/run_progress.py` - Progress tracking helpers
- `app/services/seeding.py` - Database seeding logic
- `app/use_cases/registry.py` - Static registry of 10 use cases
- `app/use_cases/<slug>/` - Each use case module (data_generation, raw_data, schemas, service, etc.)
- `app/ai/` - 6 AI adapters (autogluon, ocr, ollama, openai, web_search)
- `app/scripts/` - generate_data.py, migrate.py, seed.py, ai_check.py
- `models/` - Trained AI models (AutoGluon artifacts for all 5 ML use cases)

### Frontend (`frontend/`)
- `src/App.tsx` - Main layout (sidebar + routes + startup strip)
- `src/api.ts` - API client + TypeScript interfaces (1162 lines, all types)
- `src/useCases.ts` - Static use case registry (10 items)
- `src/startupTraining.ts` - Startup status polling hooks
- `src/fraudPredictionQuality.ts` - Fraud score classification helpers
- `src/main.tsx` - React entry point
- `src/styles.css` - Tailwind imports
- `index.html` - HTML entry
- `vite.config.ts` - Vite configuration
- `tsconfig.json` - TypeScript config

### Data (`data/`)
- `fraud_detection/` - raw/train/, raw/val/, raw/test/
- `credit_risk/` - raw/train/, raw/val/, raw/test/
- `document_ocr/` - raw/customer_0001/ through customer_0012/
- `support_chatbot/` - raw/policies/, raw/procedures/, raw/faq/, raw/notices/, raw/evaluation/
- `liquidity_forecast/` - raw/timeseries/, raw/calendar/, raw/policies/
- `aml_monitoring/` - raw/train/, raw/val/, raw/test/, raw/network/, raw/entities/, raw/case_notes/
- `kyc_kyb/` - raw/individual/, raw/business/, raw/watchlists/, raw/policies/
- `email_automation/` - raw/customers/, raw/events/, raw/campaigns/, raw/templates/, raw/policies/, raw/evaluation/
- `market_intelligence/` - raw/news/, raw/rates/, raw/competitors/, raw/calendar/, raw/snapshot/, raw/taxonomy/, raw/evaluation/
- `workflow_orchestration/` - raw/cases/, raw/definitions/, raw/contracts/, raw/policies/, raw/evaluation/
- Each folder has `metadata.json` and `ground_truth.json`

### Scripts (`scripts/`)
- `setup-backend.cjs` - Creates .venv + installs Python deps
- `python.cjs` - Runs .venv Python (cross-platform)
- `wait-for-backend.cjs` - Waits for /api/ready before starting frontend
- `free-dev-ports.cjs` - Kills stale processes on ports 8001/5173

### Models (`backend/models/`)
- `fraud-detection/autogluon/` - Trained fraud detection model
- `credit-risk/autogluon/` - Trained credit risk model
- `kyc-kyb/autogluon/` - Trained KYC/KYB model
- `aml-monitoring/autogluon/` - Trained AML model
- `liquidity-forecast/autogluon-timeseries/` - Trained liquidity forecast model
- Configured via `backend/app/config.py` → `storage_dir = Path("models")`

## Development Commands

### Setup
```powershell
# Full setup (Node + Python + data + DB)
npm run setup
npm run data:generate
npm run db:migrate
npm run db:seed
npm run ai:check
```

### Development
```powershell
# Full stack (backend + frontend)
npm run dev:full
# or
npm run full

# Backend only
npm run dev:backend

# Frontend only
npm run dev:frontend

# Stop all
npm run dev:stop
```

### Database
```powershell
# Generate data
npm run data:generate

# Migrate
npm run db:migrate

# Seed
npm run db:seed

# Check AI adapters
npm run ai:check
```

### Testing
```powershell
# Full test suite
npm run test:full

# Backend only
npm --prefix backend run test

# Frontend only
npm --prefix frontend run test
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:admin123@localhost:5432/banking_ai` | PostgreSQL connection |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Default model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Local LLM |
| `LOCAL_MODEL_TIMEOUT_SECONDS` | `30` | Ollama timeout |
| `AUTOGLUON_PRESET` | `good_quality` | Quality preset |
| `AUTOGLUON_TIME_LIMIT_SECONDS` | `180` | Training time limit |
| `AUTOGLUON_NUM_BAG_FOLDS` | `0` | Bag folds (0=disabled) |
| `AUTOGLUON_NUM_CPUS` | `1` | CPUs for AutoGluon |
| `SKIP_STARTUP_TRAINING` | `0` | Skip startup ML |
| `FORCE_RETRAIN` | `0` | Force retraining |
| `MARKET_LIVE_SEARCH_ENABLED` | `1` | Live web search |
| `MARKET_RESEARCH_MODEL` | `gpt-5.4-mini` | Research model |
| `MARKET_SEARCH_FALLBACK_MODEL` | `gpt-5-search-api` | Fallback model |
| `MARKET_SEARCH_CONTEXT_SIZE` | `low` | Context size |
| `MARKET_MAX_SEARCH_CALLS_STARTUP` | `6` | Max startup calls |
| `MARKET_MAX_SEARCH_CALLS_USER_RUN` | `10` | Max user calls |
| `MARKET_MAX_SEARCH_CALLS_DEEP` | `16` | Max deep calls |
| `MARKET_SEARCH_TIMEOUT_SECONDS` | `45` | Search timeout |

## Quick Decision Log

1. **AutoGluon Time Limit**: Set to 180s for local dev (was 600s, too slow on this workstation)
2. **Bag Folds**: Set to 0 (disabled) for speed (was 5, too slow)
3. **Num CPUs**: Set to 1 (this workstation has limited cores)
4. **Startup Pipeline**: Sequential (not parallel) because AutoGluon fits share a local lock
5. **User Run Queue**: Separate from startup queue to prevent blocking
6. **Fallback Strategy**: Ollama first, GPT-4o fallback (not mock scores)
7. **OCR**: pdfplumber/PyMuPDF first, GPT-4o fallback for scanned/image-only
8. **Liquidity Forecast**: AutoGluon TimeSeries first, deterministic baseline fallback
9. **Market Intelligence**: Live web search first, synthetic corpus fallback when API unavailable
10. **Workflow Orchestration**: Reads upstream outputs, does not retrain/rerun models
11. **Data Language**: All English (no Turkish in code/schemas/data)
12. **File Naming**: snake_case for Python files, kebab-case for API slugs, camelCase for TS vars
13. **No Auth**: Local demo system, no authentication implemented
14. **No Email Sending**: Email Automation is draft-only, no real SMTP
15. **Port Management**: 8001 (backend), 5173 (frontend), auto-free on startup

## Navigation Guide

### Working on a Specific Stage
When modifying a specific use case, read these files:

**Fraud Detection (Stage 1)**:
- Backend: `backend/app/use_cases/fraud_detection/` (training.py, service.py, schemas.py, metrics.py)
- Frontend: `frontend/src/App.tsx` -> `FraudDetectionPage()` function
- API: `backend/app/api/use_cases.py` -> fraud routes
- Data: `data/fraud_detection/raw/`

**Credit Risk (Stage 2)**:
- Backend: `backend/app/use_cases/credit_risk/`
- Frontend: `frontend/src/App.tsx` -> `CreditRiskPage()`
- API: `backend/app/api/use_cases.py` -> credit routes
- Data: `data/credit_risk/raw/`

**Document OCR (Stage 3)**:
- Backend: `backend/app/use_cases/document_ocr/`, `backend/app/ai/ocr_adapter.py`
- Frontend: `frontend/src/App.tsx` -> `DocumentOcrPage()`
- API: `backend/app/api/use_cases.py` -> document routes
- Data: `data/document_ocr/raw/customer_*/`

**Support Chatbot (Stage 4)**:
- Backend: `backend/app/use_cases/support_chatbot/`, `backend/app/ai/ollama_qwen_adapter.py`
- Frontend: `frontend/src/App.tsx` -> `SupportChatbotPage()`
- API: `backend/app/api/use_cases.py` -> support routes (chat endpoint)
- Data: `data/support_chatbot/raw/`

**Liquidity Forecast (Stage 5)**:
- Backend: `backend/app/use_cases/liquidity_forecast/`, `backend/app/ai/autogluon_timeseries_adapter.py`
- Frontend: `frontend/src/App.tsx` -> `LiquidityForecastPage()`
- API: `backend/app/api/use_cases.py` -> liquidity routes
- Data: `data/liquidity_forecast/raw/`

**AML Monitoring (Stage 6)**:
- Backend: `backend/app/use_cases/aml_monitoring/`
- Frontend: `frontend/src/App.tsx` -> `AmlMonitoringPage()`
- API: `backend/app/api/use_cases.py` -> aml routes
- Data: `data/aml_monitoring/raw/`

**KYC/KYB (Stage 7)**:
- Backend: `backend/app/use_cases/kyc_kyb/`
- Frontend: `frontend/src/App.tsx` -> `KycKybPage()`
- API: `backend/app/api/use_cases.py` -> kyc routes
- Data: `data/kyc_kyb/raw/`

**Email Automation (Stage 8)**:
- Backend: `backend/app/use_cases/email_automation/`
- Frontend: `frontend/src/App.tsx` -> `EmailAutomationPage()`
- API: `backend/app/api/use_cases.py` -> email routes (draft endpoint)
- Data: `data/email_automation/raw/`

**Market Intelligence (Stage 9)**:
- Backend: `backend/app/use_cases/market_intelligence/`, `backend/app/ai/web_search_adapter.py`
- Frontend: `frontend/src/App.tsx` -> `MarketIntelligencePage()`
- API: `backend/app/api/use_cases.py` -> market routes (research endpoint)
- Data: `data/market_intelligence/raw/`

**Workflow Orchestration (Stage 10)**:
- Backend: `backend/app/use_cases/workflow_orchestration/`
- Frontend: `frontend/src/App.tsx` -> `WorkflowOrchestrationPage()`
- API: `backend/app/api/use_cases.py` -> workflow routes (orchestrate endpoint)
- Data: `data/workflow_orchestration/raw/`

### Cross-Cutting Changes
- **New API endpoint**: `backend/app/api/use_cases.py`
- **New database table**: `backend/app/db/models.py` + `backend/app/scripts/migrate.py`
- **New AI adapter**: `backend/app/ai/` (new file + `backend/app/api/health.py`)
- **New frontend page**: `frontend/src/App.tsx` (add route + page component)
- **New frontend type**: `frontend/src/api.ts`
- **New data generation**: `backend/app/use_cases/<slug>/data_generation.py` + `backend/app/scripts/generate_data.py`
- **Environment change**: `.env` + `backend/app/config.py`

## Session Handoff Protocol

### When Starting a New Session
1. Read .context/CONTEXT.md completely
2. Check `.context/HISTORY.md` for the last 3-5 entries to understand recent context
3. Check `.context/STAGES.md` for specific stage details if working on one
4. Update `.context/AGENTS.md` if new rules discovered

### When Ending a Session
1. Append entry to `.context/HISTORY.md` with:
   - Date, AI model, session summary
   - Files modified (with full paths)
   - Decisions made (why X instead of Y)
   - Errors encountered and how fixed
   - Learnings (project-specific tips)
   - Next session recommendations
2. Update `Current State` and `Active TODOs` sections in .context/CONTEXT.md
3. Update `.context/STAGES.md` if any stage details changed
4. Clean up `.agent_test/` (delete temporary files)
4. Confirm all updates to user

### When Switching AI Models
- Read `.context/AGENTS.md` first (it contains model-agnostic instructions)
- Then read `.context/CONTEXT.md`
- Then `.context/HISTORY.md` (last 5 entries)
- Only read `.context/STAGES.md` if working on a specific stage

## Common Gotchas

1. **AutoGluon Lock**: All AutoGluon fits share a local lock. Don't try to train fraud and credit simultaneously.
2. **Port 8001/5173**: If already in use, run `npm run dev:stop` or `npm run dev:full` (auto-frees)
3. **WinError 10048**: Windows port conflict. Kill process manually if `dev:stop` fails.
4. **Ollama Timeout**: Default 30s. Increase to 60s if model is slow. GPT-4o will fallback automatically.
5. **Data Generation**: All files are deterministic. Delete `data/` and re-run `npm run data:generate` to regenerate.
 6. **Model Retraining**: Delete `backend/models/<slug>/autogluon` and restart to force retrain.
7. **Database Reset**: `npm run db:migrate` recreates tables. `npm run db:seed` repopulates.
8. **Skip Training**: Set `SKIP_STARTUP_TRAINING=1` in `.env` for frontend-only dev.
9. **Frontend Waits**: Frontend waits for `/api/ready` (not just `/api/health`) before starting.
10. **JSONB Storage**: All ML payloads stored as JSONB. Use `payload['key']` in queries.

---

**End of CONTEXT.md** - Next, read STAGES.md for stage-specific details.
