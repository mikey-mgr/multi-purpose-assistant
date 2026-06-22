# Automated Talent Matching Pipeline

AI-powered pipeline that ingests unstructured listing data from regional employment platforms, performs relevance classification against candidate profiles, generates optimised documents, emails via Gmail SMTP, and sends WhatsApp notifications.

## Architecture

```
listing sources ──► scrapers ──► PostgreSQL ──► matcher ──► generator ──► email / WhatsApp
                                    ▲                                    ▲
                                    └── user profile (RAG) ───────────────┘
```

Two decoupled stages:
1. **Matcher** (`app/matcher.py`) — cheap LLM batch-classifies unscored jobs as matched/rejected
2. **Generator** (`app/orchestrator.py`) — single LLM call per matched job outputs resume JSON + cover letter + apply_details. Renders PDF via RenderCV + DOCX cover letter. Saves to `job_matches` + `generated_documents`.

Three entry points:
- **Library** — import `app.*` directly (no Prefect needed)
- **Prefect flows** — scheduled/triggered orchestration with retries + UI
- **WhatsApp webhook** — FastAPI server receives job posting images via WhatsApp

## Project Structure

```
├── app/                       # Core logic (imported by flows)
│   ├── orchestrator.py        # process_job_for_user(), batch_process_applications()
│   ├── matcher.py             # batch_match_jobs()
│   ├── llm.py                 # LLM calls (OpenRouter / Gemini) + generate_text_multimodal()
│   ├── rag.py                 # Profile assembly + hybrid search
│   ├── rendercv_renderer.py   # YAML → PDF (RenderCV)
│   ├── document_generator.py  # Cover letter DOCX
│   ├── email_sender.py        # Gmail SMTP sender
│   ├── whatsapp_notifier.py   # WhatsApp message sender
│   ├── config.py              # Settings from env vars / Prefect secrets
│   ├── schemas.py             # Pydantic models
│   ├── apply_agent.py         # WhatsApp notification composition
│   └── webhook_server.py      # FastAPI: POST /api/webhooks/whatsapp-image
├── core/
│   └── database.py            # SQLAlchemy models + CRUD + vector search
├── scrapers/                  # Data ingestion modules
├── prefect_flows/
│   ├── job_pipeline.py        # 4 flows: scrape-and-store, match-jobs, generate-matched, apply-agent
│   ├── whatsapp_job_flow.py   # process-whatsapp-job: image→parse→match→generate→email→WhatsApp
│   ├── deployment.py          # Register + serve all 5 deployments
│   └── setup_blocks.py        # Prefect Secret blocks from .env
├── scripts/
│   └── seed_prompts.py        # Programmatic prompt seed (upserts)
└── db_configs/migrations/
    └── init.sql               # Full schema + pgvector
```

## Quick Setup

### 1. Database
```bash
psql -U postgres -f db_configs/migrations/init.sql
```

### 2. Environment (`.env`)
```
DB_CONN_URI=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ai_assistant
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=...
LLM_MODEL=openai/gpt-4o
```

### 3. Seed prompts
```bash
python scripts/seed_prompts.py
```

## Deployments

Run `python prefect_flows/deployment.py` to serve all 5 deployments:

| Name | Schedule | Description |
|------|----------|-------------|
| `01-scraper` | `0 7-21/2 * * *` | Ingest listings from regional platforms. Auto-chains 02→03→04 when scheduled. Manual runs stop at ingest. |
| `02-matcher` | — | Batch-classify unscored jobs |
| `03-generator` | — | Generate docs for matched jobs |
| `04-apply-agent` | — | Send emails + WhatsApp notifications |
| `05-whatsapp-image-job` | — | Parse job image from webhook → apply → notify (triggered via FastAPI) |

## Prefect 3 Setup

Requires two conda environments: `prefect_env` (full stack) and `data_eng` (library only).

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

**Terminal 3 — Worker** (keep running):
```bash
conda activate prefect_env
python -m prefect_flows.deployment
```
Registers all 5 deployments and starts an in-process runner.

**Manual run** (any terminal):
```bash
conda activate prefect_env
prefect deployment run 01-scraper
prefect deployment run 02-matcher
prefect deployment run 05-whatsapp-image-job
```

**Conda environments:**
| Env | Installs | Use for |
|-----|----------|---------|
| `data_eng` | `requirements.txt` minus `prefect` | App logic, scrapers, tests |
| `prefect_env` | `requirements.txt` (full) | Prefect server + workers + deployment |

## WhatsApp Job Webhook

Start the FastAPI server:
```bash
python -m app.webhook_server          # default port 8000
```

Your WhatsApp host sends:
```http
POST http://localhost:8055/api/webhooks/whatsapp-image
apikey: your_api_key

{"imageBase64": "<base64>", "mimetype": "image/jpeg"}
```

The server validates the API key, image size (≤10MB) and type (jpeg/png/webp/gif), then triggers the `process-whatsapp-job` flow which:
1. Sends image + user profile to Gemini vision in one LLM call
2. Parses job fields, match score, resume overrides, cover letter, apply_details, and WhatsApp text
3. Inserts ScrapedJob (`site='whatsapp'`) + JobMatch
4. Renders resume PDF + cover letter DOCX
5. Emails application if `proceed=apply_now` + action=email
6. Sends WhatsApp notification with score + gaps + outcome
7. Sets status to `applied` or `waiting` (needs_docs/needs_info)

On failure at any step, an error WhatsApp is sent back.

### Per-job flow

```
01-scraper (cron) ──► 02-matcher ──► 03-generator ──► 04-apply-agent
                          ▲                                  ▲
                          │                                  │
05-whatsapp-image-job ────┘                                  │
(webhook trigger)                                            │
                                                             ▼
                                                    WhatsApp notification
```

## Key Modules

| Module | What it does |
|--------|-------------|
| `core.database` | ORM models, CRUD, pgvector hybrid search, prompt management |
| `app.llm` | `generate_text()`, `generate_text_multimodal()`, `generate_embedding()` — routes through OpenRouter or Gemini |
| `app.orchestrator` | `process_job_for_user()` — RAG → LLM → YAML → PDF → snapshot |
| `app.rag` | Profile assembly + hybrid (keyword + semantic) job search |
| `app.rendercv_renderer` | YAML dict → RenderCV PDF |
| `app.email_sender` | Gmail SMTP (no test redirect) |
| `app.whatsapp_notifier` | WhatsApp Cloud API messages |

## Provider Override

Each stage targets an independent provider + model:

| Scenario | match_provider | match_model | generate_provider | generate_model |
|----------|---------------|-------------|-------------------|----------------|
| Default | *(→ LLM_PROVIDER)* | `openai/gpt-4o-mini` | *(→ LLM_PROVIDER)* | *(→ LLM_MODEL)* |
| Match via Gemini, generate via GPT-4o | `gemini` | `gemini-2.0-flash` | `openrouter` | `openai/gpt-4o` |

## Source of Truth vs Generated Artifacts

| What | Stored in |
|------|-----------|
| Raw profile | `users`, `work_experience`, `education`, `projects`, `skills`, `certifications` |
| Per-job rewrite | LLM output (discarded after YAML) |
| Final resume PDF | `generated_documents` table + `data/rendercv_output/` |

## Hybrid Search

```sql
score = ts_rank(fulltext_keywords) * 0.5 + (1 - cosine_distance(embedding)) * 0.5
```

Keyword: PostgreSQL `tsvector` with GIN index. Semantic: `vector(1536)` pgvector cosine distance.

## Prompts

System prompts stored in DB `prompts` table and seeded via `scripts/seed_prompts.py`:

| Prompt | Purpose |
|--------|---------|
| `job_matcher_v1` | Batch-classify unscored jobs |
| `ats_and_cover_v1` | Resume JSON + cover letter + apply_details + gap analysis |
| `whatsapp_notify_batch_v1` | Compose WhatsApp notifications for batch results |
| `whatsapp_image_job_v1` | Parse job image → match → generate → WhatsApp text (multimodal) |
