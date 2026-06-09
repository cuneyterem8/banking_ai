# AGENTS.md — AI Assistant Instructions for Banking AI Portal

> **AI INSTRUCTION**: This file is tool-agnostic. Whether you are Claude Code, Cursor, Copilot, Codex, Qwen, Kimi, or any other AI assistant, read this file first to understand how to behave in this project.

---

## Role & Context

You are an AI coding assistant working on the **Banking AI Portal** — a local-first staged MVP with 10 banking AI use cases. The project uses FastAPI (backend), React (frontend), PostgreSQL (database), and AutoGluon/Ollama/OpenAI (AI adapters).

---

## Context Loading Protocol

### Step 1: Read AGENTS.md (This File)
Understand the rules and workflow before any action.

### Step 2: Read .context/CONTEXT.md
- Get project overview, current state, active TODOs
- Understand file structure, navigation guide, common gotchas
- Check development environment details

### Step 3: Check .context/HISTORY.md
- Read the **last 3-5 entries** to understand recent context
- Do not repeat work already done in previous sessions
- Check for unresolved errors or blockers

### Step 4: Read .context/STAGES.md (Only If Needed)
- If working on a specific stage, read that stage's section
- If cross-cutting changes, check API endpoint map and database schema
- Do NOT read the entire file unless necessary — it is large

---

## Memory Bank Update Protocol

### After EVERY Task (File Edit, Code Change, etc.)
1. **Append to .context/HISTORY.md** immediately with:
   - Date, AI model, tool name
   - What changed (files, lines, purpose)
   - Any errors encountered and how fixed
   - Decisions made (why X instead of Y)

### After EVERY Session
1. **Update .context/CONTEXT.md**:
    - Update `Current State` section if project status changed
    - Update `Active TODOs` (mark completed items, add new items)
    - Update `Last Updated` timestamp
2. **Update .context/HISTORY.md**:
   - Write a full session entry using the template
   - Include next session recommendations
3. **Confirm updates to user** before ending the session

### When Switching AI Models
1. Read .context/AGENTS.md (this file)
2. Read .context/CONTEXT.md (full)
3. Read .context/HISTORY.md (last 5 entries)
4. Only read .context/STAGES.md if working on a specific stage

---

## Code Style & Conventions

### Language
- **All English**: Code, comments, schemas, data, variable names are in English
- No Turkish in source code (user is Turkish but project is English-only)

### File Naming
- **Python**: `snake_case` (e.g., `fraud_detection/training.py`)
- **API Slugs**: `kebab-case` (e.g., `fraud-detection`)
- **TypeScript**: `camelCase` for variables, `PascalCase` for components

### Backend (Python)
- Use **type hints** everywhere
- Use **Pydantic models** for all API schemas
- Use **SQLModel** for database models
- Use **async/await** for I/O operations
- Use **httpx** for HTTP calls (not requests)
- Handle errors gracefully with try/except + logging

### Frontend (TypeScript/React)
- Use **functional components** with hooks
- Use **TanStack Query** for data fetching
- Use **Tailwind CSS** for styling
- Use **lucide-react** for icons
- Use **recharts** for charts
- Use **react-router-dom** for routing

### Database
- Use **JSONB** for flexible ML payloads
- Use `payload['key']` to access JSONB fields
- Keep timestamps in UTC

---

## Safety Rules

### ❌ NEVER Do These
1. **Never run `git commit`, `git push`, `git reset`, `git rebase` unless explicitly asked**
   - Ask for confirmation every time: "Should I commit these changes?"
2. **Never modify files outside the working directory**
   - Working directory: `C:\Users\cnytC\Desktop\code_projects\banking_ai`
 3. **Never delete `data/` or `backend/models/` without user confirmation**
   - These contain deterministic data and trained models
4. **Never expose secrets**
   - Do not print `.env` contents, API keys, or database credentials
5. **Never assume the user wants production code**
   - This is a local demo system; ask before adding auth, rate limiting, etc.
6. **Never create test/draft/temp files outside `.agent_test/`**
   - All temporary, test, draft, or experimental files MUST go in `.agent_test/`
   - Do NOT clutter `backend/`, `frontend/`, or root with `.test.py`, `.draft.ts`, `temp_*` files

### ✅ ALWAYS Do These
1. **Always test after making changes**
   - Run `npm run test:full` or relevant tests
   - Verify backend starts: `npm run dev:backend`
   - Verify frontend starts: `npm run dev:frontend`
2. **Always update HISTORY.md after changes**
3. **Always confirm destructive actions**
   - "I will delete X files, is that okay?"
4. **Always prefer minimal changes**
   - Do not refactor unrelated code
   - Do not add features not requested
5. **Always follow the existing code style**
   - Match indentation, naming, and patterns in surrounding code

---

## Navigation Guide

### When Working on a Specific Stage

**Example: Fraud Detection (Stage 1)**
1. Read `STAGES.md` → Fraud Detection section
2. Read backend files: `backend/app/use_cases/fraud_detection/training.py`, `service.py`, `schemas.py`
3. Read frontend: `frontend/src/App.tsx` → `FraudDetectionPage()` function
4. Read API: `backend/app/api/use_cases.py` → fraud routes
5. Read data: `data/fraud_detection/raw/`

**General Rule**: 
- Backend logic: `backend/app/use_cases/<slug>/`
- Frontend page: `frontend/src/App.tsx` (search for `<Slug>Page`)
- API routes: `backend/app/api/use_cases.py`
- Data files: `data/<folder>/raw/`
- AI adapter: `backend/app/ai/<adapter>_adapter.py`

### Cross-Cutting Changes
- **New API endpoint**: `backend/app/api/use_cases.py`
- **New database table**: `backend/app/db/models.py` + `backend/app/scripts/migrate.py`
- **New AI adapter**: `backend/app/ai/` + `backend/app/api/health.py`
- **New frontend page**: `frontend/src/App.tsx` + `frontend/src/api.ts`
- **New data generation**: `backend/app/use_cases/<slug>/data_generation.py` + `backend/app/scripts/generate_data.py`
- **Environment change**: `.env` + `backend/app/config.py`

---

## Common Gotchas (AI-Specific)

1. **AutoGluon Lock**: All AutoGluon fits share a local threading lock. Do not try to trigger multiple training runs simultaneously.
2. **Port 8001/5173**: If already in use, run `npm run dev:stop` or `npm run dev:full` (auto-frees).
3. **WinError 10048**: Windows port conflict. Kill process manually if `dev:stop` fails.
4. **Ollama Timeout**: Default 30s. If Ollama is down, GPT-4o will fallback automatically (if API key is set).
5. **Data Generation**: All files are deterministic. If data seems corrupted, delete `data/` and run `npm run data:generate`.
 6. **Model Retraining**: Delete `backend/models/<slug>/autogluon` and restart to force retrain.
7. **Database Reset**: `npm run db:migrate` recreates tables. `npm run db:seed` repopulates.
8. **Skip Training**: Set `SKIP_STARTUP_TRAINING=1` in `.env` for frontend-only dev.
9. **Frontend Waits**: Frontend waits for `/api/ready` (not just `/api/health`) before starting.
10. **JSONB Storage**: All ML payloads stored as JSONB. Use `payload['key']` in queries.

---

## Tool-Specific Notes

### Claude Code
- Use `CLAUDE.md` as project rules (if supported)
- This `AGENTS.md` file is equivalent

### Cursor
- Use `.cursorrules` or `AGENTS.md` (Cursor reads both)
- This file is in the project root, so Cursor will pick it up

### GitHub Copilot
- Copilot with `AGENTS.md` support will read this file automatically
- Ensure instructions are in the file before starting work

### Codex / Qwen / Kimi / Other
- These files are plain Markdown, so any tool can read them
- Follow the same context loading protocol

---

## Quick Reference: Important File Paths

| Purpose | Path |
|---------|------|
| Project root | `C:\Users\cnytC\Desktop\code_projects\banking_ai` |
| Backend entry | `backend/app/main.py` |
| Frontend entry | `frontend/src/main.tsx` |
| API routes | `backend/app/api/use_cases.py` |
| Database models | `backend/app/db/models.py` |
| AI adapters | `backend/app/ai/` |
| Use cases | `backend/app/use_cases/` |
| Data directory | `data/` |
| Model storage | `backend/models/` |
| Test directories | `.agent_test/backend_tests/` (Python), `.agent_test/frontend_tests/` (TypeScript) |
| Scripts | `scripts/` |
| Environment | `.env` |
| Python deps | `requirements.txt` (root) - All deps (FastAPI + AutoGluon + ML)
| Context file | `.context/CONTEXT.md` |
| Stage details | `.context/STAGES.md` |
| Session history | `.context/HISTORY.md` |
| AI instructions | `.context/AGENTS.md` (this file) |
| AI workspace | `.agent_test/` — Temporary test/draft files (see .agent_test/README.md) |

---

## End of Session Checklist

Before ending any session, confirm:
- [ ] .context/HISTORY.md updated with session entry
- [ ] .context/CONTEXT.md updated (Current State, TODOs, Last Updated)
- [ ] .context/STAGES.md updated if any stage details changed
- [ ] .agent_test/ cleaned up (temporary files deleted)
- [ ] All file changes tested (if applicable)
- [ ] User informed of all updates

---

**End of AGENTS.md** — Start every session by reading CONTEXT.md.
