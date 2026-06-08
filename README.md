# Banking AI Portal

Local-first staged MVP for 10 banking AI use cases. All app-facing text, source comments, schemas, and synthetic sample content are in English.

## Current Stage

Stage 8 is implemented: **Fraud Detection**, **Credit Risk**, **Document OCR**, **Support Chatbot**, **Liquidity Forecast**, **AML Monitoring**, **KYC/KYB**, and **Email Automation**.

The other two use cases are visible in the sidebar as planned stages and will be implemented after manual approval of the previous stage.

## Data directory

All synthetic raw files and database seed inputs live under [`data/`](data/). `npm run data:generate` writes deterministic XLSX, PDF, JPG, JSON, and metadata files for active use cases:

- Fraud Detection: `data/fraud_detection/raw/train/`, `val/`, and `test/`
- Credit Risk: `data/credit_risk/raw/train/`, `val/`, and `test/`
- Document OCR: `data/document_ocr/raw/customer_0001/` through `customer_0012/`, plus manifest and ground truth JSON
- Support Chatbot: `data/support_chatbot/raw/` policy PDFs, Markdown procedures, FAQ JSON, notices, evaluation questions, plus manifest and ground truth JSON
- Liquidity Forecast: `data/liquidity_forecast/raw/` cash time-series Excel, holiday/campaign CSV files, cash policy PDF, plus manifest and ground truth JSON
- AML Monitoring: `data/aml_monitoring/raw/` train/val/test AML alert Excel files, transaction network workbook, entity JSON, case notes PDF, plus metadata and ground truth JSON
- KYC/KYB: `data/kyc_kyb/raw/` individual and business onboarding packages, reference watchlists, document policy PDF, plus metadata and ground truth JSON
- Email Automation: `data/email_automation/raw/` customer events JSON, customer/campaign Excel files, templates, compliance policy PDFs, evaluation cases, plus metadata and ground truth JSON

```powershell
npm run data:generate
npm run db:seed
```

## Prerequisites

- Node.js 24+
- Python 3.11+
- Local PostgreSQL running outside the app

## Setup

```powershell
npm run setup
npm run data:generate
```

Create the PostgreSQL database if it does not exist yet, then copy `.env.example` to `.env` and set `DATABASE_URL` (default user `postgres`, password `admin123`, database `banking_ai`).

```powershell
npm run db:migrate
npm run db:seed
npm run ai:check
npm run dev:full
```

`npm run full` is an alias for `npm run dev:full`. The frontend waits for `http://127.0.0.1:8001/api/ready` (database reachable, API accepting traffic) before starting. The eight-stage startup pipeline continues in the background; poll `GET /api/ml-ready`, `GET /api/startup/status`, or each use case `training-status` endpoint to see when models and deterministic startup outputs are ready.

Heavy ML jobs use separate startup and user-run queues. Startup runs sequentially in this order: Fraud Detection, Credit Risk, Document OCR, Support Chatbot, Liquidity Forecast, AML Monitoring, KYC/KYB, Email Automation. User-triggered runs can execute after that use case's own startup stage completes while later startup stages continue. AutoGluon fit operations still share a local lock so they do not compete for Ray workers and RAM at the same time.

If port `8001` is already in use (`WinError 10048`), run `npm run dev:stop` or `npm run dev:full` (it frees ports 8001 and 5173 automatically before starting).

For local dev on this workstation, `AUTOGLUON_TIME_LIMIT_SECONDS=180`, `AUTOGLUON_NUM_BAG_FOLDS=0`, and `AUTOGLUON_NUM_CPUS=1` keep startup training practical. Increase these values in `.env` when you want slower, higher-quality retraining.

`npm run setup:backend` creates a project-root `.venv` and installs `backend/requirements.txt` plus `backend/requirements-ai.txt` (AutoGluon included). All backend npm scripts use that virtual environment automatically.

Frontend: `http://localhost:5173`

Backend: `http://localhost:8001`

## Active models

- On backend startup (`npm run dev:full`), prior processed outputs for the first eight implemented use cases are cleared, then the eight startup stages run sequentially.
- Fraud Detection trains on **train** (2560), calibrates threshold and validation metrics on **val** (640), then scores **test** (800) via **Run Fraud Model**. **PR-AUC** is the primary score.
- Credit Risk trains on **train** (1920), calibrates threshold and validation metrics on **val** (480), then scores **test** (600) via **Run Credit Risk Model**. **ROC-AUC** is the primary score.
- Document OCR performs deterministic startup extraction over 60 synthetic banking documents with pdfplumber/PyMuPDF first and GPT-4o fallback for scanned/image-only artifacts when configured. **Run Document OCR** reruns extraction.
- Support Chatbot performs deterministic startup evaluation over the generated question set. **Ask Support Chatbot** and **Run Support Evaluation** use BM25 retrieval over 8 synthetic support documents, then Ollama Qwen first with GPT-4o fallback.
- Liquidity Forecast performs startup forecast generation. **Run Liquidity Forecast** reruns the held-out forecast flow, attempting AutoGluon TimeSeries when available and otherwise using a deterministic local seasonal baseline.
- AML Monitoring trains on **train** (1600), calibrates validation metrics on **val** (400), and drafts top validation narratives at startup. **Run AML Monitoring** scores **test** (500) and drafts narratives for the highest-risk held-out alerts. **PR-AUC** is the primary score.
- KYC/KYB extracts synthetic onboarding documents, applies deterministic policy rules, trains on **train** (32), calibrates validation metrics on **val** (8), then scores **test** (8) via **Run KYC/KYB Verification**. **PR-AUC** is the primary score.
- Email Automation runs a startup evaluation over 24 synthetic generation cases, creates service and campaign drafts, applies deterministic compliance rules, and persists provider/scoring details. **Run Email Automation** reruns the evaluation set, while the Draft Workspace creates one persisted synthetic draft at a time. No real email sending is implemented.
- Dataset includes **27 transaction features** (device, IP, merchant risk, velocity, authentication, geography, and more).
- Credit Risk includes **23 applicant/raw underwriting fields** plus labels and synthetic loss-given-default.
- Document OCR includes **12 customer packages**, each with bank statement, account confirmation, income proof, scanned statement PDF, and transfer notice JPG.
- Support Chatbot includes **8 knowledge documents**, **26 deterministic chunks**, and **8 evaluation questions**.
- Liquidity Forecast includes **6 branch/ATM series**, **180 history days**, **14 holdout forecast days**, holiday/campaign calendars, and a cash inventory policy PDF.
- AML Monitoring includes **2500 synthetic alerts**, transaction network sheets, entity relationships, suspicious activity notes, typology labels, and SAR recommendation ground truth.
- KYC/KYB includes **48 onboarding packages**, **288 generated documents**, sanctions and jurisdiction reference files, document policy rules, and manual-review ground truth.
- Email Automation includes **120 synthetic customers**, **80 service events**, **40 campaign audience rows**, **24 evaluation cases**, compliance policy PDFs, brand/tone guidelines, and no-send draft ground truth.
- Optional env: `SKIP_STARTUP_TRAINING=1`, `FORCE_RETRAIN=1`.
- After changing data files, delete the matching model folder under `storage/models/` and restart the backend.

If AutoGluon is not available, active ML pages show a clear adapter setup error instead of mock scores.
