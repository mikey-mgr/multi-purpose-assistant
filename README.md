# Automated Job Application Assistant

AI-powered pipeline that scrapes Zimbabwean job boards, retrieves relevant job postings, generates ATS-optimised resumes and cover letters, and produces ready-to-send PDF/DOCX documents.

## What this project actually is

It's **two things that work together but don't depend on each other**:

### 1. `app/` + `core/` — The Python Library
This is the engine. It's just Python code you can import and run directly:
```python
from app.orchestrator import process_job_for_user
process_job_for_user(user_id="xxx", job_id=123)   # runs now
```
It scrapes jobs → stores them in PostgreSQL → fetches a user's profile → calls an LLM to rewrite sections → builds a RenderCV YAML → renders a PDF → snapshots everything in `generated_documents`. Zero infrastructure needed beyond PostgreSQL.

### 2. `prefect_flows/` — The Scheduler (Optional)
Prefect is a separate background worker that calls the same `app.*` functions on a cron schedule. It adds:
- **Scheduling**: runs the pipeline every 6 hours automatically
- **Retries**: if an LLM call fails, retries with backoff
- **Logging & observability**: UI at http://localhost:4200
- **Secret management**: API keys stored in Prefect's encrypted database instead of `.env`

You can run the library *without* Prefect (python script, cron job, notebook). Prefect is just a more robust way to automate it.

### Architecture diagram

```
┌─────────────────────┐
│ Job Scrapers (6h)   │  ← scrapers/*.py (iharare, vacancybox, vacancymail)
│  unified_scraper    │
└──────────┬──────────┘
           │ raw job postings (inserted via core.database.insert_jobs)
           ▼
┌─────────────────────┐
│ PostgreSQL          │  ← db_configs/migrations/init.sql
│  ai_assistant       │
│   ├─ scraped_jobs   │  ← hybrid search: tsvector (keyword) + vector (semantic)
│   ├─ users          │
│   ├─ resumes        │  ← vector(1536) on summary, experience, projects
│   ├─ work_experience│
│   ├─ projects       │
│   ├─ education      │
│   ├─ certifications │
│   ├─ skills         │
│   └─ prompts        │  ← versioned system prompts for LLM
└──────────┬──────────┘
           │ fetch unprocessed jobs via app.rag
           ▼
┌─────────────────────┐
│ Orchestrator        │  ← app/orchestrator.py
│  (Prefect flow)     │  ← prefect_flows/job_pipeline.py
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  1. Assemble user profile (RAG)      │  ← app/rag.py
│  2. Build prompt from template       │  ← core.database.build_prompt()
│  3. Call LLM (gpt-4 / etc.)          │  ← app/llm.py
│  4. Generate PDF resume              │  ← app/document_generator.py
│  5. Generate DOCX cover letter       │
│  6. Store in generated_documents/    │
└──────────────────────────────────────┘
```

## Project Structure

```
├── app/                    # Core application logic (prefect imports from here)
│   ├── config.py           # Settings (env vars → Prefect Secrets fallback)
│   ├── schemas.py          # Pydantic models
│   ├── llm.py              # LLM prompt building + API calls
│   ├── rag.py              # RAG retrieval: profile assembly + hybrid job search
│   ├── document_generator.py  # PDF (weasyprint) + DOCX (python-docx) output
│   └── orchestrator.py     # process_job_for_user() — full pipeline
├── core/
│   ├── database.py         # SQLAlchemy models + CRUD + vector search helpers
│   └── __init__.py
├── scrapers/               # Job board scrapers (standalone CLI or unified)
│   ├── iharare_scraper.py
│   ├── vacancybox_scraper.py
│   ├── vacancymail_scraper.py
│   └── unified_scraper.py
├── prefect_flows/          # Prefect deployment (decoupled from app)
│   ├── job_pipeline.py     # Flows: pull-and-process-jobs, manual-generate
│   └── deployment.py       # Build + register deployment
├── db_configs/migrations/
│   └── init.sql            # Full PostgreSQL schema + extensions
├── scripts/
│   ├── seed_prompts.sql    # Raw SQL seed for system prompts
│   └── seed_prompts.py     # Programmatic seed (upserts by name)
└── requirements.txt
```

## Setup

### 1. Dependencies

```bash
pip install -r requirements.txt
```

**Two conda environments (recommended):**

| Env | Installs | Purpose |
|-----|----------|---------|
| `data_eng` | `requirements.txt` minus `prefect` | Run scrapers, app logic, tests |
| `prefect_env` | `requirements.txt` (full) | Run Prefect server + workers |

### 2. Database

Requires PostgreSQL 15+ with `pgvector` installed.

```bash
# Create DB, extensions, tables, indexes, triggers, and the RAG view
psql -U postgres -f db_configs/migrations/init.sql
```

### 3. Seed system prompts

```bash
# SQL route
psql -U postgres -d ai_assistant -f scripts/seed_prompts.sql

# Or Python route
python scripts/seed_prompts.py
```

### 4. Environment variables (`.env`)

```
DB_CONN_URI=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ai_assistant
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
EMBEDDING_MODEL=text-embedding-3-small
PREFECT_API_URL=http://localhost:4200/api
```

## Pipeline (end-to-end)

```
scrapers ──► scraped_jobs ──► orchestator ──► LLM (per-section rewrites)
                              │                    │
                              │                    ▼
                              │           build_yaml_dict()
                              │           (DB data + LLM overrides)
                              │                    │
                              │                    ▼
                              │           rendercv render ──► PDF
                              │                    │
                              │                    ▼
                              │           generated_documents table
                              │           (snapshot: YAML + PDF path +
                              │            prompt_name + model + tokens)
```

### Source of truth vs generated artifacts

| What | Stored in | Purpose |
|------|-----------|---------|
| Raw profile data | `users`, `work_experience`, `education`, `projects`, `skills`, `certifications` | Source of truth — never modified by the pipeline |
| Rewritten sections | LLM output parsed into JSON | Per-job ATS optimisation, discarded after YAML is built |
| Final resume YAML + PDF | `generated_documents` table + `data/rendercv_output/` | Snapshot of exactly what was sent to which job |

The child tables (`work_experience`, `education`, etc.) are **never overwritten** by the generation pipeline. Each run creates a new row in `generated_documents` linking `resume_id` (the source version) and `job_id` (the target job).

## Usage

### Run scrapers (standalone)

```bash
python -m scrapers.iharare_scraper
python -m scrapers.vacancymail_scraper
python -m scrapers.vacancybox_scraper
python -m scrapers.unified_scraper    # all three
```

See `scrapers/README.md` for detailed scraper docs.

### Run generation pipeline (one shot, no Prefect)

```bash
python -c "
from app.orchestrator import process_job_for_user
docs = process_job_for_user(user_id='YOUR_USER_UUID', job_id=123)
print(f'Generated {len(docs)} documents')
"
```

## API Keys & Security

### Dependency pinning

Prefect 3.7.x requires `fastapi<0.115.0` (Starlette < 1.0.0) for `PrefectRouter` compatibility.
These are pinned in `requirements.txt`.

### ` .env` is NOT safe for production

The `.env` file stores keys as **plaintext on disk**. Anyone with access to your machine or repo backup can read them. Use it only for local testing.

### Prefect Secret Blocks (production)

Prefect stores secrets in its own database (SQLite or PostgreSQL), encrypted at rest. Only the Prefect server API can read them — your code never sees the raw `.env` file.

## Prefect 3 Setup

The pipeline uses **Prefect 3.x**. Some commands changed from v2.

> **Note**: If `conda run` fails, use the full Python path directly:
> ```
> & "C:\Users\mmash\.conda\envs\prefect_env\python.exe" -m prefect server start
> ```

### Step-by-step

**Terminal 1 — API server** (keep running):
```bash
conda activate prefect_env
prefect server start
```
Opens UI at http://localhost:4200.

**Terminal 2 — Secrets** (one-time, server running):
```bash
conda activate prefect_env
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
python -m prefect_flows.setup_blocks
```
Fill in real API keys in `.env` first — the script reads them and creates
[Prefect Secret blocks](http://localhost:4200/blocks) (one per key).

**Terminal 3 — Scheduled runner** (keep running):
```bash
conda activate prefect_env
python -m prefect_flows.deployment
```
Registers a deployment with `0 */6 * * *` cron (Africa/Harare) and starts
an in-process runner. Scheduled flow runs execute inside this process.

**Manual run** (any terminal):
```bash
conda activate prefect_env
python -m prefect_flows.job_pipeline --manual <user_id> <job_id>
```

### How your code reads them

```python
from app.config import settings
settings = settings.from_prefect()  # reads Prefect blocks first, falls back to .env
print(settings.OPENAI_API_KEY)      # from Prefect block or .env
```

### What to do with `.env`

1. Fill in real values in `.env` for local development
2. Once everything works via Prefect, **delete `.env`** for production
3. The `.env` file is already in `.gitignore` — it will never be committed

## Hybrid Search

```sql
score = ts_rank(fulltext_keywords) * 0.5 + (1 - cosine_distance(embedding)) * 0.5
```

- **Keyword**: PostgreSQL `tsvector` with GIN index, auto-populated via trigger on `scraped_jobs`
- **Semantic**: `vector(1536)` column using pgvector cosine distance (populated async)
- Falls back gracefully to pure full-text if no embedding available

## RenderCV Setup

PDF resumes use [RenderCV](https://github.com/sinaatalay/rendercv) with the `harvard` theme.

```bash
pip install rendercv
rendercv --version          # should show 2.8.x
```

RenderCV requires [Typst](https://github.com/typst/typst/releases) for PDF generation.
Add `typst.exe` to your PATH (Windows) or `brew install typst` (macOS).

Verify: `typst --version`

### Output structure

```
data/
  rendercv_output/
    {user_snake_case_name}_cv.pdf      # final PDF resume
    {user_snake_case_name}_cv.yaml     # generated YAML
  cover_letters/
    cover_letter_{job_id}_*.docx       # cover letter
```

## Key Modules

| Module | What it does |
|--------|-------------|
| `core.database` | SQLAlchemy ORM models, `insert_jobs()`, vector search, prompt CRUD |
| `app.llm` | `generate_text()` + `generate_embedding()` — OpenAI |
| `app.rag` | `assemble_user_profile()` + `find_relevant_jobs()` — retrieval |
| `app.rendercv_renderer` | `build_yaml_dict()` + `render()` — YAML assembly + PDF generation |
| `app.orchestrator` | `process_job_for_user()` — full pipeline (RAG → LLM → YAML → PDF → snapshot) |
| `app.document_generator` | Cover letter DOCX output |
| `prefect_flows` | Scheduled + manual Prefect flow definitions |
