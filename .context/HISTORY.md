# HISTORY.md - Banking AI Portal Session History

> **AI INSTRUCTION**: Append a new entry at the end of this file after EVERY session. Read the last 3-5 entries when starting a new session to understand recent context.

---

## Session History

### [2026-06-09] Session: Kimi (OpenCode) — Backend files reorganized: requirements, test artifacts, pytest config

**Summary**: Moved requirements.txt (merged with requirements-ai.txt into single file), pytest.ini, and preview_banking_ai.db to correct locations to clean up the backend directory and centralize all test artifacts in `.agent_test/`.

**Files Moved**:
- `backend/requirements.txt` → `requirements.txt` (root directory, merged with requirements-ai.txt)
- `backend/pytest.ini` → `.agent_test/backend_tests/pytest.ini` (test config)
- `backend/preview_banking_ai.db` → `.agent_test/preview_banking_ai.db` (test database)

**Config Changes**:
- `scripts/setup-backend.cjs`: Updated paths from `backend/requirements.txt` to `requirements.txt` (root)

**Documentation Updated**:
- `.context/CONTEXT.md`: Moved requirements.txt references from `Backend` section to `Root Level` section
- `.agent_test/README.md`: Updated directory structure to include pytest.ini and preview_banking_ai.db
- `README.md`: Updated file tree (removed requirements from backend, added to root)
- `.context/AGENTS.md`: Quick reference updated with test directories

**Decisions Made**:
- requirements.txt (merged with requirements-ai.txt) belongs in root because it's project-wide dependency
- pytest.ini belongs with tests in `.agent_test/backend_tests/`
- preview_banking_ai.db is a test artifact, so it belongs in `.agent_test/`
- setup-backend.cjs now references root-level requirements files

---

### [2026-06-09] Session: Kimi (OpenCode) — Tests and READMEs moved to .agent_test/

**Summary**: Moved all test directories and stray README files from the main project to `.agent_test/` to keep the project clean and follow the workspace organization rules.

**Files Moved**:
- `backend/tests/` (47 test files + __pycache__) → `.agent_test/backend_tests/` — Python backend tests
- `frontend/src/useCases.test.ts` → `.agent_test/frontend_tests/useCases.test.ts` — Frontend test
- `data/README.md` → `.agent_test/README-data.md` — Data directory documentation
- `backend/.pytest_cache/` → `.agent_test/pytest_cache/` — pytest cache

**Config Changes**:
- `backend/package.json`: `"test"` script updated to point to `..\\.agent_test\\backend_tests`
- `frontend/package.json`: `"test"` script updated to point to `..\\.agent_test\\frontend_tests`
- `backend/app/config.py`: `storage_dir` changed from `Path("../storage")` to `Path("models")`

**Test Code Updates**:
- `.agent_test/backend_tests/conftest.py`: Added `sys.path` manipulation to insert `backend/` directory so imports like `from app.db.models import ...` work correctly from the new location

**Documentation Updated**:
- `.context/CONTEXT.md`: Updated file structure references (tests → .agent_test/backend_tests/)
- `.context/AGENTS.md`: Added test directories to quick reference table
- `.agent_test/README.md`: Added comprehensive test directory documentation with running instructions
- `README.md`: Updated file tree (removed `tests/` from backend, added `models/`)

**Decisions Made**:
- All tests centralized in `.agent_test/` to avoid cluttering main codebase
- Backend tests still need `backend/` in Python path for `app.*` imports
- Frontend tests moved to `.agent_test/frontend_tests/` for consistency
- All stray README files consolidated in `.agent_test/`
- `pytest_cache/` is now in `.agent_test/` (not `backend/.pytest_cache/`)

---

### [2026-06-09] Session: Kimi (OpenCode) — Models moved to backend/ + storage/ removed

**Summary**: Moved AI trained models from `storage/models/` to `backend/models/` since they are consumed by the backend. Updated all code references and config. Removed empty `storage/` directory.

**Files Moved**:
- `storage/models/aml-monitoring/` → `backend/models/aml-monitoring/`
- `storage/models/credit-risk/` → `backend/models/credit-risk/`
- `storage/models/fraud-detection/` → `backend/models/fraud-detection/`
- `storage/models/kyc-kyb/` → `backend/models/kyc-kyb/`
- `storage/models/liquidity-forecast/` → `backend/models/liquidity-forecast/`
- `storage/` directory removed (empty after move)

**Config Changes**:
- `backend/app/config.py`: `storage_dir` changed from `Path("../storage")` to `Path("models")`
- This makes models resolve to `backend/models/` relative to backend working directory

**Code References Updated** (removed redundant `/models/` segment from paths):
- `backend/app/use_cases/fraud_detection/training.py`
- `backend/app/use_cases/credit_risk/training.py`
- `backend/app/use_cases/kyc_kyb/training.py`
- `backend/app/use_cases/aml_monitoring/training.py`
- `backend/app/use_cases/liquidity_forecast/forecasting.py`
- `backend/app/api/health.py`
- `backend/app/scripts/ai_check.py`

**Database local_path Updated**:
- `backend/app/services/ml_training_manager.py`: `storage/models/...` → `models/...`
- `backend/app/use_cases/kyc_kyb/service.py`: `storage/models/...` → `models/...`
- `backend/app/use_cases/aml_monitoring/service.py`: `storage/models/...` → `models/...`
- `backend/tests/test_run_cleanup.py`: `storage/models/...` → `models/...`

**Documentation Updated**:
- `.context/CONTEXT.md`: Updated storage references to `backend/models/`
- `.context/AGENTS.md`: Updated storage references to `backend/models/`
- `.context/PROMPT.md`: Updated storage references to `backend/models/`
- `.context/STAGES.md`: Updated storage references to `backend/models/`
- `.context/HISTORY.md`: Updated storage references to `backend/models/`
- `README.md`: Updated storage references to `backend/models/`

**Decisions Made**:
- Models are backend artifacts, so they belong in `backend/` not project root
- `storage_dir` config changed to `Path("models")` so it resolves to `backend/models/` relative to backend working directory
- Removed redundant `/models/` segment from all code paths since `storage_dir` now directly points to `models/` directory
- `storage/` directory was completely removed (was empty after previous log cleanup)

---

### [2026-06-09] Session: Kimi (OpenCode) — Storage cleanup + .agent_test setup

**Summary**: Moved all temporary log files, screenshots, and other dev artifacts from `storage/` and root to `.agent_test/` as part of the workspace organization. `storage/` now only contains persistent AI models (`models/` directory). Root directory is clean of all log files.

**Files Moved**:
- `storage/dev-backend*.log` (4 files) → `.agent_test/` — Backend dev logs
- `storage/dev-frontend*.log` (4 files) → `.agent_test/` — Frontend dev logs
- `storage/dev-full*.log` (4 files) → `.agent_test/` — Full stack logs
- `storage/dev-full-smoke.*.log` (2 files) → `.agent_test/` — Smoke test logs
- `storage/screenshots/` (2 PNG files) → `.agent_test/screenshots/` — UI test screenshots
- `.codex_logs/dev-full-aml.*` (3 files) → `.agent_test/` — Codex runtime logs
- `.codex_logs/` directory removed (empty after move)

**Files Not Moved** (intentionally kept in storage/):
- `backend/models/` — Persistent AI trained models (aml-monitoring, credit-risk, fraud-detection, kyc-kyb, liquidity-forecast)

**Decisions Made**:
- `backend/models/` is persistent and valuable, must stay in `backend/`
- All `.log` files are temporary runtime outputs, belong in `.agent_test/`
- Screenshots are test artifacts, belong in `.agent_test/`
- `.agent_test/` is gitignored so these won't clutter git history

**Files Modified**:
- `.gitignore` — Added `.agent_test/` entry
- `.agent_test/README.md` — Created workspace rules
- `.context/AGENTS.md` — Updated file paths and added `.agent_test` rule
- `.context/PROMPT.md` — Updated file paths and added `.agent_test` rule
- `.context/CONTEXT.md` — Updated file paths and added `.agent_test` reference
- `.context/HISTORY.md` — Updated file paths
- `.context/STAGES.md` — Updated file paths
- `README.md` — Updated prompt reference path

---

### [2026-06-09] Session: Kimi (OpenCode) — Initial README + Context Files

**Summary**: Deep project exploration followed by comprehensive README.md rewrite and creation of 4-file Memory Bank context system (CONTEXT.md, STAGES.md, HISTORY.md, AGENTS.md).

**Files Modified**:
- `README.md` (rewritten) — Complete overhaul with architecture, 10 stage details, API map, tech stack, setup guide, troubleshooting
- `CONTEXT.md` (created) — Main AI context file with project overview, current state, file structure, navigation guide, session handoff protocol
- `STAGES.md` (created) — Deep-dive stage details for all 10 use cases
- `HISTORY.md` (created) — This file (session history template)
- `AGENTS.md` (created) — AI tool instructions and rules

**Decisions Made**:
- Adopted 4-file Memory Bank pattern (inspired by GitHub research: project-butler, agent-markdown-memory-bank-protocol, codebase-context-spec)
- CONTEXT.md serves as single source of truth for project overview
- STAGES.md serves as deep-dive reference for individual stages
- HISTORY.md is append-only for session continuity
- AGENTS.md contains model-agnostic instructions for any AI tool
- AI will auto-update HISTORY.md and CONTEXT.md at session end

**Errors Encountered**:
- Permission denied during initial file write attempts (plan mode restrictions)
- Resolved by switching to build mode after user confirmation

**Learnings**:
- Project uses 10-stage sequential startup pipeline with AutoGluon lock
- Frontend waits for `/api/ready` (not just `/api/health`) before starting
- All synthetic data is deterministic (seeded generation)
- JSONB columns store all ML payloads for flexibility
- User is Turkish but all code/content is English

**Next Session Recommendations**:
- Consider implementing high-priority TODOs: startup time optimization, adapter error handling, caching layer
- Add frontend tests for all 10 use case pages (currently only App.tsx tested)
- Review STAGES.md for accuracy when modifying any stage

---

## Session Entry Template

### [YYYY-MM-DD] Session: AI Model (Tool) — Brief Description

**Summary**: What was accomplished in this session.

**Files Modified**:
- `path/to/file` — What changed and why
- `path/to/another/file` — What changed

**Decisions Made**:
- Decision 1 (why X instead of Y)
- Decision 2

**Errors Encountered**:
- Error description — How it was fixed

**Learnings**:
- Project-specific tip or discovery
- Another learning

**Next Session Recommendations**:
- What should be done next
- Any blockers or dependencies

---

**End of HISTORY.md** — Next, read .context/AGENTS.md for AI instructions.
