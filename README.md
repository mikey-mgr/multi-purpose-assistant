# Automated Talent Matching Pipeline

AI-powered pipeline that ingests unstructured listing data from regional employment platforms, performs relevance classification against candidate profiles, generates optimised documents, emails via Gmail SMTP, and sends WhatsApp notifications.

## Relationship Nurturing System

The pipeline is extended with a **relationship nurturing layer** that bridges your job applications with your personal network. Three features built on a shared contact architecture:

| # | Feature | Status |
|---|---------|--------|
| 7 | **Referral Bridge** — cross-reference job matches against contacts at the same company, with AI-generated outreach messages sent via WhatsApp | **Active** |
| 9 | **Contact Architecture** — 10 tables storing strategic profile data (profession, family, education, groups, interactions, milestones) | Schema ready, no data |
| 10 | **Daily Reminder Engine** — morning milestone/stale-contact digest + evening interaction log prompt | Stubbed, disabled (`_ENABLED = False`) |

## Architecture

```
listing sources ──► scrapers ──► PostgreSQL ──► matcher ──► generator ──► email / WhatsApp
                                    ▲                                    ▲
                                    └── user profile (RAG) ───────────────┘

                                    ┌── contacts ──► referral bridge (#7) ──► WhatsApp referral alerts
PostgreSQL ──► job_matches ────────┤
               scraped_jobs         └── milestones ──► reminder engine (#10) ──► WhatsApp daily digest
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
│   ├── webhook_server.py      # FastAPI: POST /api/webhooks/whatsapp-image
│   ├── contact_manager.py     # #7 Referral matching + #9 Contact CRUD + import
│   └── reminder_engine.py     # #10 Stub: daily nurturing reminders (_ENABLED = False)
├── core/
│   └── database.py            # SQLAlchemy models + CRUD + vector search + relationship tables
├── scrapers/                  # Data ingestion modules
├── prefect_flows/
│   ├── job_pipeline.py        # 4 flows: scrape-and-store, match-jobs, generate-matched, apply-agent
│   ├── whatsapp_job_flow.py   # process-whatsapp-job: image→parse→match→generate→email→WhatsApp
│   ├── relationship_flows.py  # #7 check-referrals flow (active) + #10 daily-reminder flow (stub)
│   ├── deployment.py          # Register + serve all 5 deployments
│   └── setup_blocks.py        # Prefect Secret blocks from .env
├── scripts/
│   └── seed_prompts.py        # Programmatic prompt seed (upserts)
└── db_configs/migrations/
    ├── init.sql               # Core schema + pgvector
    └── add_relationship_tables.sql  # #9 Contact + referral + milestone tables
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

> Alternatively, set keys via environment variables (skip `.env`):
> ```powershell
> # PowerShell
> $env:DB_CONN_URI="postgresql://postgres:YOUR_PASSWORD@localhost:5432/ai_assistant"
> $env:OPENROUTER_API_KEY="sk-or-..."
> $env:GEMINI_API_KEY="..."
> $env:LLM_PROVIDER="openrouter"
> ```
> ```cmd
> :: CMD
> set DB_CONN_URI=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ai_assistant
> set OPENROUTER_API_KEY=sk-or-...
> set GEMINI_API_KEY=...
> set LLM_PROVIDER=openrouter
> ```
> Set these in the same terminal before running any Python commands. They persist only for that session.

### 3. Seed prompts
```bash
python scripts/seed_prompts.py
```

## Deployments

Run `python prefect_flows/deployment.py` to serve all 7 deployments:

| Name | Schedule | Description |
|------|----------|-------------|
| `01-scraper` | `0 7-19/3 * * *` | Ingest listings from regional platforms. Auto-chains 02→03→04 when scheduled. Manual runs stop at ingest. |
| `02-matcher` | — | Batch-classify unscored jobs |
| `03-generator` | — | Generate docs for matched jobs |
| `04-apply-agent` | — | Send emails + WhatsApp notifications |
| `05-whatsapp-image-job` | — | Parse job image from webhook → apply → notify (triggered via FastAPI) |
| `06-check-referrals` | — | **#7** Cross-reference matches against contacts; sends WhatsApp referral alerts |
| `07-daily-reminder` | — | **#10** Daily nurturing reminders (stub — not scheduled; enable in `reminder_engine.py`) |

## Prefect 3 Setup

Requires two conda environments: `prefect_env` (full stack) and `data_eng` (library only).

**Terminal 1 — API server** (keep running):
```bash
conda activate prefect_env
prefect server start
```
Opens UI at http://localhost:4200.

**Terminal 2 — Secrets** (one-time, server running):
# Get keys currently in  env - activate prefect_env then:
python -c "from app.config import settings; print(repr(settings.GEMINI_API_KEY))"

Option A — from `.env` file:
```bash
conda activate prefect_env
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
python -m prefect_flows.setup_blocks
```

Option B — from terminal env vars (skip `.env`):
```powershell
conda activate prefect_env
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
$env:OPENROUTER_API_KEY="sk-or-..."
$env:GEMINI_API_KEY="..."
$env:DB_CONN_URI="postgresql://postgres:pass@localhost:5432/ai_assistant"
$env:LLM_PROVIDER="openrouter"
$env:LLM_MODEL="openai/gpt-4o"
python -m prefect_flows.setup_blocks
```
Set env vars for any other keys in the script (`SERPAPI_API_KEY`, `GMAIL_ADDRESS`, etc.) as needed. The script reads from the environment first; `.env` is only a fallback.

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

## Relationship Nurturing System

Three features built on top of the job pipeline — described below from most to least ready.

---

### #7 — Referral Bridge (active)

When a job match is found, checks if any contact in your network works at that company (via `contacts.current_company`). If so:

1. Records the opportunity in `job_referral_opportunities`
2. Calls the LLM to generate a natural referral-ask message
3. Sends a WhatsApp alert with the job + contact + suggested message

**Run manually:**
```bash
prefect deployment run 06-check-referrals
```

**Key files:**
- `app/contact_manager.py` — `check_new_match_for_referrals()`, `check_all_matches_for_referrals()`, `generate_referral_message()`
- `prefect_flows/relationship_flows.py` — `check-referrals` flow
- `core/database.py` — `find_referral_opportunities_for_job()`, `find_all_referral_opportunities()`, `JobReferralOpportunity` model

**To get value:** Add contacts with `current_company` filled. Use `import_contacts_bulk()` or direct SQL INSERT.

---

### #9 — Contact Architecture (schema ready, data empty)

10 tables storing your network's strategic data. Run the migration to create them:

```bash
psql -d ai_assistant -f db_configs/migrations/add_relationship_tables.sql
```

| Table | Purpose | Key fields for #7 |
|-------|---------|-------------------|
| `contacts` | Your network (not the same as `users` — that's you) | `current_company`, `job_title`, `email`, `phone` |
| `contact_profiles` | Layer 2/3 strategic data | `professional_summary`, `business_interests`, `hobbies`, `birthday`, `relationship_strength` |
| `contact_family` | Spouse/kids info | `family_member_name`, `relationship`, `birthday` |
| `contact_education` | Schools attended | `institution`, `degree_type`, `graduation_year` |
| `contact_groups` | Categories ("Professional", "Church", "Neighbours") | `group_name` |
| `contact_group_memberships` | Many-to-many contacts ↔ groups | — |
| `contact_interactions` | Log every call/message/meeting | `interaction_type`, `direction`, `value_provided`, `follow_up_date` |
| `contact_milestones` | Birthdays, work anniversaries | `milestone_type`, `milestone_date` |
| `contact_outreach_suggestions` | AI-generated conversation starters | `suggestion_type`, `content`, `rating` |
| `job_referral_opportunities` | Auto-populated by #7 | `status`, `reached_out_at`, `response` |

**Views (read-only queries):**
- `referral_opportunities` — joins matches + jobs + contacts
- `stale_contacts` — no interaction in 60+ days
- `upcoming_milestones` — next 14 days, unacknowledged

**Populating contacts:**
```python
from app.contact_manager import import_contacts_bulk

contacts = [
    {"first_name": "John", "last_name": "Smith", "email": "john@example.com",
     "current_company": "Econet", "job_title": "Data Engineer", "source": "manual"},
]
created, updated = import_contacts_bulk(contacts)
```

---

### #10 — Daily Reminder Engine (stubbed, disabled)

Sits in `app/reminder_engine.py` with `_ENABLED = False` at the top. Function signatures are complete but all return `None`.

**When enabled** (`_ENABLED = True`), the `daily-reminder` flow will:
- **Morning:** WhatsApp digest of upcoming milestones + stale contacts + AI conversation starters
- **Evening:** Prompt to log today's interactions

```python
# app/reminder_engine.py
_ENABLED = False  # flip to True, then schedule the flow
```
