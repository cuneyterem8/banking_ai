# Banking AI Portal - Data Directory

Single source of truth for synthetic raw artifacts and database seed inputs.

## Layout

```
data/
  <use_case_folder>/          # snake_case (e.g. fraud_detection)
    metadata.json
    raw/
      train/                  # ML training (XLSX only)
      val/                    # ML validation (80/20 split from former train pool)
      test/                   # Held-out evaluation

  document_ocr/
    metadata.json             # manifest preview and checksums
    ground_truth.json         # expected fields and table rows
    raw/
      customer_0001/
        bank_statement.pdf
        account_confirmation.pdf
        income_proof.pdf
        scanned_statement.pdf
        transfer_notice.jpg

  support_chatbot/
    metadata.json             # knowledge manifest and checksums
    ground_truth.json         # expected evaluation sources and citations
    raw/
      policies/               # synthetic policy PDFs
      procedures/             # synthetic Markdown procedures
      faq/                    # synthetic FAQ JSON
      notices/                # synthetic product notice text
      evaluation/             # deterministic support questions

  liquidity_forecast/
    metadata.json             # cash time-series manifest and checksums
    ground_truth.json         # synthetic holdout actuals for forecast validation
    raw/
      timeseries/             # history and holdout actuals in one workbook
      calendar/               # holiday and campaign CSV files
      policies/               # synthetic cash inventory policy PDF
```

API slugs use kebab-case (`fraud-detection`); folder names use snake_case (`fraud_detection`).

Fraud Detection counts: **2560 train**, **640 val**, **800 test** (4000 total synthetic rows, 27 raw fields plus engineered features).

Credit Risk counts: **1920 train**, **480 val**, **600 test** (3000 total synthetic applications, 23 applicant/raw underwriting fields plus labels and synthetic loss-given-default).

Document OCR counts: **12 customer packages**, **60 documents** (36 digital PDFs, 12 scanned statement PDFs, 12 scanned-style transfer notice JPG files).

Support Chatbot counts: **8 knowledge documents**, **26 chunks**, **8 evaluation questions** (policy PDFs, Markdown procedures, FAQ JSON, product notice, and evaluation JSON).

Liquidity Forecast counts: **6 branch/ATM series**, **1080 history records**, **84 holdout actuals**, **7 calendar events**, and **6 raw artifacts** including metadata and ground truth.

## Commands

```powershell
npm run data:generate   # write XLSX/PDF/JPG/MD/TXT/JSON under data/
npm run db:seed         # load files into PostgreSQL raw_* tables
```

Generated XLSX, PDF, JPG, Markdown, TXT, and JSON raw files are gitignored; run `data:generate` after clone.

## Use cases

| Folder | Stage | Status |
|--------|-------|--------|
| fraud_detection | 1 | Active |
| credit_risk | 2 | Active |
| document_ocr | 3 | Active |
| support_chatbot | 4 | Active |
| liquidity_forecast | 5 | Active |
| aml_monitoring through workflow_orchestration | 6-10 | Placeholder |
