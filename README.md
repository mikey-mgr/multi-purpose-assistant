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

WhatsApp user ──► Evolution API ──► webhook server ──► rule-based router
                    (localhost:8080)   (port 8055)      (ends with ? = query, else = job)
                                                          │
                                    ┌─────────────────────┤
                                    ▼                     ▼
                          process-whatsapp-text    process-whatsapp-job
                          (parse + generate +      (vision + parse +
                           send)                    generate + send)
```

Three entry points:
- **Library** — import `app.*` directly (no Prefect needed)
- **Prefect flows** — scheduled/triggered orchestration with retries + UI
- **WhatsApp webhook** — FastAPI server receives job postings (images + text) via Evolution API

## Project Structure

```
├── app/                       # Core logic (imported by flows)
│   ├── orchestrator.py        # process_job_for_user(), batch_process_applications()
│   ├── matcher.py             # batch_match_jobs()
│   ├── llm.py                 # LLM calls (OpenRouter / Gemini) + generate_text_multimodal()
│   ├── rag.py                 # Profile assembly + hybrid search + reference handling
│   ├── rendercv_renderer.py   # YAML → PDF (RenderCV) + reference injection
│   ├── document_generator.py  # Cover letter DOCX + merged PDF builder
│   ├── email_sender.py        # Gmail SMTP sender
│   ├── whatsapp_notifier.py   # WhatsApp message + document sender
│   ├── config.py              # Settings from env vars / Prefect secrets
│   ├── schemas.py             # Pydantic models
│   ├── apply_agent.py         # WhatsApp notification composition
│   ├── webhook_server.py      # FastAPI: POST /api/webhooks/evolution (replaces n8n)
│   ├── contact_manager.py     # #7 Referral matching + #9 Contact CRUD + import
│   ├── reminder_engine.py     # #10 Stub: daily nurturing reminders (_ENABLED = False)
│   └── secrets_store.py       # OS credential manager (Windows Credential Manager via keyring)
├── core/
│   └── database.py            # SQLAlchemy models + CRUD + vector search + relationship tables
├── scrapers/                  # Data ingestion modules
├── prefect_flows/
│   ├── job_pipeline.py        # 4 flows: scrape-and-store, match-jobs, generate-matched, apply-agent
│   ├── whatsapp_job_flow.py   # Image + text WhatsApp flows: parse → match → generate → email → WhatsApp
│   ├── relationship_flows.py  # #7 check-referrals flow (active) + #10 daily-reminder flow (stub)
│   ├── deployment.py          # Register + serve all 6 deployments
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

### 2. Secrets

Secrets are resolved in this priority order:
1. **OS env vars** — session-level override (`$env:KEY=val`)
2. **OS Credential Manager** (via `keyring`) — primary storage for local dev
3. **Prefect Secret Blocks** — legacy, when server is reachable
4. **`.env` file** — fallback only (gitignored)

**Recommended — store in Windows Credential Manager:**
```powershell
pip install keyring
python -m app.secrets_store set OPENROUTER_API_KEY
python -m app.secrets_store set DB_CONN_URI
```

Each command prompts for the value (hidden input). Stored in OS credential manager, not in any file.

**Legacy — `.env` file** (only used if keyring has no value):
```
DB_CONN_URI=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ai_assistant
LLM_PROVIDER=openrouter
```

**Legacy — env vars** (highest priority, session-only):
```powershell
$env:OPENROUTER_API_KEY="sk-or-..."
```

### 3. Seed prompts
```bash
python scripts/seed_prompts.py
```

## Deployments

Run `python prefect_flows/deployment.py` to serve all 6 deployments:

| Name | Schedule | Description |
|------|----------|-------------|
| `01-scraper` | `0 7-19/3 * * *` | Ingest listings from regional platforms. Pass `chain_next=True` to trigger 02→03→04. |
| `02-matcher` | — | Batch-classify unscored jobs |
| `03-generator` | — | Generate docs for matched jobs |
| `04-apply-agent` | — | Batch-process generated matches: send emails + WhatsApp notifications |
| `05-whatsapp-image-job` | — | Parse job image from Evolution API webhook → apply → notify |
| `05b-whatsapp-text-job` | — | Parse job text from Evolution API webhook → apply → notify |
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
Registers all 6 deployments and starts an in-process runner.

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

## WhatsApp Webhook (replaces n8n)

Start the FastAPI server:
```bash
python -m app.webhook_server          # port 8055
```

The server listens for webhooks from **Evolution API** at `http://localhost:8080`:

```http
POST http://localhost:8055/api/webhooks/evolution
apikey: your_whatsapp_api_key

{
  "event": "messages.upsert",
  "instanceId": "...",
  "data": {
    "key": { "remoteJid": "263771906135@s.whatsapp.net", "fromMe": false },
    "message": { "conversation": "..." }  // or "imageMessage": {...}
  }
}
```

### Routing

The server:
1. Drops messages where `fromMe = true` or chat is not an individual (group/broadcast/status)
2. Drops messages from phone numbers not in the allowed prefix list `[263788667111, 263773393934, 263771906135]`
3. Routes based on message type:
   - **Image messages** → `process-whatsapp-job` (vision LLM call)
   - **Text messages** → rule-based intent router:
     - Ends with `?` → data query (show matches, answer questions, handle greetings)
     - Otherwise → `process-whatsapp-text` (parse job posting + generate + apply)

### Image flow (`process-whatsapp-job`)

1. Sends image + user profile to Gemini vision in one LLM call
2. Parses job fields, match score, resume overrides, cover letter, apply_details, and WhatsApp text
3. Inserts ScrapedJob (`site='whatsapp'`) + JobMatch
4. Renders resume PDF + cover letter DOCX
5. Emails application if `proceed=apply_now` + action=email + no cooldown
6. Sends WhatsApp notification with score + gaps + outcome
7. Sets status to `applied` or `waiting` (needs_docs/needs_info)

### Text flow (`process-whatsapp-text`)

Same as image flow but:
- Uses text-only LLM call instead of vision
- Parses job posting from raw text
- After job processing, sends a WhatsApp message back including the `whatsapp_text` field from the LLM output

### Data query flow

When a message ends with `?`, the server:
1. Fetches the 20 most recent non-rejected job matches (with job URLs)
2. Sends them to the `whatsapp_data_query_v1` prompt
3. Returns a conversational answer via WhatsApp

### Cooldown

The system applies a **7-day cooldown** per recipient email address to avoid spamming the same employer:

| State | Behaviour |
|-------|-----------|
| Cooldown active (`cooldown_until > now`) | Email skipped, WhatsApp says "cooldown until YYYY-MM-DD" |
| Cooldown expired, job scraped during cooldown | `expired_discard` — job is stale, discarded |
| Cooldown expired, job newer than cooldown | Email sent normally |

Keyed on `(recipient_email, user_id)`. Stored in `email_cooldowns` table.

### Per-job flows

```
01-scraper (cron) ──► 02-matcher ──► 03-generator ──► 04-apply-agent
                          ▲                                  ▲
                          │                                  │
05-whatsapp-image-job ────┘                                  │
(webhook trigger)                                            │
                                                             ▼
05b-whatsapp-text-job ────┘                         WhatsApp notification
(webhook trigger)
```

## Key Modules

| Module | What it does |
|--------|-------------|
| `core.database` | ORM models, CRUD, pgvector hybrid search, prompt management, cooldown tracking |
| `app.llm` | `generate_text()`, `generate_text_multimodal()`, `generate_embedding()` — routes through OpenRouter or Gemini |
| `app.orchestrator` | `process_job_for_user()` — RAG → LLM → YAML → PDF → snapshot; `batch_process_applications()` — batch email + WhatsApp |
| `app.rag` | Profile assembly + hybrid (keyword + semantic) job search + reference management |
| `app.rendercv_renderer` | YAML dict → RenderCV PDF (Harvard theme) + server-side reference injection |
| `app.document_generator` | Cover letter DOCX + merged PDF builder |
| `app.email_sender` | Gmail SMTP (no test redirect) |
| `app.whatsapp_notifier` | WhatsApp Cloud API messages + documents |

## Provider Override

Each stage targets an independent provider + model:

| Scenario | match_provider | match_model | generate_provider | generate_model |
|----------|---------------|-------------|-------------------|----------------|
| Default | *(→ LLM_PROVIDER)* | `nvidia/nemotron-3-ultra-550b-a55b:free` | *(→ LLM_PROVIDER)* | *(→ LLM_MODEL)* |
| Match via Gemini, generate via GPT-4o | `gemini` | `gemini-2.0-flash` | `openrouter` | `openai/gpt-4o` |

## Source of Truth vs Generated Artifacts

| What | Stored in |
|------|-----------|
| Raw profile | `users`, `work_experience`, `education`, `projects`, `skills`, `certifications`, `contacts` |
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
| `ats_and_cover_v1` | Resume JSON + cover letter + apply_details + gap analysis (scrape flow) |
| `whatsapp_notify_batch_v1` | Compose WhatsApp notifications for batch results |
| `whatsapp_image_job_v1` | Parse job image → match → generate → WhatsApp text (multimodal) |
| `whatsapp_text_job_v1` | Parse job text → match → generate → WhatsApp text |
| `whatsapp_data_query_v1` | Answer user data questions / handle greetings (uses recent matches) |

### Prompt rules (applied across all generate prompts)

- **Summary** opens with the employer's pain point, first-person, never states the user already works there
- **Experience bullets**: strict caps — max 3 per project entry, max 4 per experience entry (hard limits, per entry)
- **Skills**: max 4 categories, max 5 skills per category, ordered by relevance
- **References**: only included if JD explicitly asks; name = title + surname only (first name never exposed to AI); phone/email injected server-side
- **User photo**: `user_photo` doc type included in `required_docs` only when JD asks for a photograph/profile picture
- **merged_pdf flag**: LLM decides if the employer wants a single merged PDF (all docs combined)

## Document Types

| Doc Type | Label | Source |
|----------|-------|--------|
| `resume` | CV / Resume | Auto-generated (generated_documents) |
| `cover_letter` | Cover Letter | Auto-generated (generated_documents) |
| `education_cert` | Education Certificate | `education.document_path` |
| `certification_cert` | Professional Certification | `certifications.document_path` |
| `id_doc` | National ID / Proof of Age | `user_documents` table |
| `drivers_license` | Driver's License | `user_documents` table |
| `portfolio_link` | Portfolio Link | `user_documents` table |
| `user_photo` | User Profile Photo | `user_documents` table |

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
| `contacts` | Your network (not the same as `users` — that's you) | `current_company`, `job_title`, `email`, `phone`, `title`, `is_reference` |
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
