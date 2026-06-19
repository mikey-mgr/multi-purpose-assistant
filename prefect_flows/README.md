# Prefect — Setup & Troubleshooting

## Prerequisites

Two conda environments:
- `data_eng` — contains `app/` and `core/` packages (the library)
- `prefect_env` — contains Prefect 3 + application dependencies

## Exact pinned versions (tested working)

In `prefect_env`:

```
prefect==3.7.4
fastapi==0.114.2        # NOT 0.115+ (Starlette 1.x breaks PrefectRouter)
starlette==0.38.6       # NOT 0.39+ (removes .routes attribute)
cyclopts>=4.8.0
rendercv[full]
typst (binary, see below)
```

Do NOT run `pip install -r requirements.txt` in `prefect_env` — it will overwrite
the pinned versions. Install packages individually.

## Three terminals — always

| Terminal | Command | Purpose |
|----------|---------|---------|
| 1 | `prefect server start` | API server + UI at :4200 |
| 2 | `python -m prefect_flows.deployment` | Registers **5 deployments** + runs scheduler |
| 3 | Free | Manual triggers |

If you stop Terminal 1 or 2, restart them in order (server first).

## First-time setup

```bash
# Terminal 1 (keep open)
conda activate prefect_env
prefect server start

# Terminal 2 (one-time, after server is up)
conda activate prefect_env
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

# Push secrets from .env into Prefect blocks
# Fill in .env with real API keys first
python -m prefect_flows.setup_blocks

# Terminal 2 continues with:
python -m prefect_flows.deployment
```

## Creating / updating secrets

Edit `.env` with the correct values, then:

```bash
python -m prefect_flows.setup_blocks
```

The script creates/overwrites Prefect Secret blocks from `.env` variables.
Empty env vars are skipped (existing blocks keep their value).

Block names used:
- `app-config-db-conn-uri`
- `app-config-openrouter-api-key`
- `app-config-gemini-api-key`
- `app-config-llm-provider`      — "openrouter" or "gemini"
- `app-config-llm-model`         — default model for generation (e.g. "openai/gpt-4o")
- `app-config-serpapi-api-key`
- `app-config-gmail-address`
- `app-config-gmail-app-password`

## Provider architecture (`app/llm.py`)

The pipeline has **two inference providers**, each with their own API key + base URL:

| Provider | Setting | API base URL |
|----------|---------|--------------|
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `gemini` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai/` |

Both are called through the **OpenAI Python SDK** (same `client.chat.completions.create` interface) — only the `base_url` and `api_key` differ. This is handled in `_get_client(provider)`.

The default provider is set by `LLM_PROVIDER` (`.env` or Prefect block `app-config-llm-provider`). You can **override per pipeline stage** via flow parameters.

### Deployments available in the UI

Visit http://localhost:4200/deployments after starting `deployment.py`:

| Deployment | Flow | Cron | Purpose |
|-----------|------|------|---------|
| `01-scraper-only` | `scrape-and-store` | `0 7-21/2 * * *` | Scrape job boards every 2 hours (7am-10pm) |
| `02-matcher-only` | `match-jobs` | — *(manual)* | Batch-classify unscored jobs |
| `03-generator-only` | `generate-matched` | — *(manual)* | Generate docs + apply (parse instructions → email / WhatsApp) |
| `04-apply-agent` | `apply-agent` | — *(manual)* | Re-run apply step for matched jobs (e.g. after email failure) |
| `job-pipeline` | `pull-and-process-jobs` | `0 7-21/2 * * *` | Match → generate → apply (every 2 hours, 7am-10pm) |

### Default parameters (set in `deployment.py`)

```json
{
  "user_id": "ff0465b9-...",
  "match_model": "openai/gpt-oss-120b:free",
  "generate_model": "models/gemini-3.1-flash-lite",
  "match_provider": "openrouter",
  "generate_provider": "gemini",
  "match_limit": 50,
  "job_limit": 10
}
```

Override any of these per run via the Prefect UI or CLI.

### Flow parameters explained

| Parameter | Applies to | Meaning |
|-----------|-----------|---------|
| `match_model` | matcher | LLM model for batch classification (should be cheap) |
| `match_provider` | matcher | `"openrouter"` or `"gemini"` — which API to route through |
| `generate_model` | generator, apply agent | LLM model for resume + cover letter + apply parsing |
| `generate_provider` | generator, apply agent | API route for generation and apply parsing |
| `match_limit` | matcher | Max **unscored** jobs to evaluate this run |
| `job_limit` | generator, apply agent | Max **matched-but-unprocessed** jobs to process this run |

**`job_limit`** controls how many matched jobs the generator processes per run.
Scraping has its own limit: [`max_pages` in scrapers/unified_scraper.py](../
scrapers/unified_scraper.py).

### Run a single stage in isolation

From the Prefect UI, click **Run** on any deployment, set only the params
you care about, and it runs independently.  For example:
- **Just re-match** existing unscored jobs → run `02-matcher-only`
- **Just regenerate** documents for already-matched jobs → run `03-generator-only`
- **Re-run apply step** (e.g. email failed) → run `04-apply-agent`

### Apply Agent (new in v4)

After generating documents (resume + cover letter), the pipeline parses
`apply_instructions` from the scraped job posting and decides what to do:

| Action | Behaviour |
|--------|-----------|
| `email` | Sends an email via Gmail SMTP with required attachments (CV, cover letter, education/certification documents as requested) |
| `external_link` | Sends a WhatsApp notification with the job details + link to apply |
| `unknown` | Sends a WhatsApp notification asking the user to review manually |

The apply agent uses an LLM call to interpret the free-text apply instructions
and extract structured data (recipient, subject, body, required document types).

**WhatsApp API** — sends to your configured number via a local HTTP endpoint:
```
POST http://localhost:8080/message/sendText/Apex_Web_Services
Header: apikey: ApexWebServiceSecretKey2026
Body: {"number": "263788667111@s.whatsapp.net", "text": "..."}
```

**Email** — uses Gmail SMTP (`smtp.gmail.com:587`) with credentials from
Prefect blocks `app-config-gmail-address` / `app-config-gmail-app-password`.  

Attached documents are collected from:
- `generated_documents.pdf_path` / `.docx_path` (resume + cover letter)
- `education.document_path` (static files in `data/education/`)
- `certifications.document_path` (static files in `data/certifications/`)

After the apply step, `job_matches.status` is updated from `'matched'` to
`'applied'` to prevent re-processing.

### Test the Python modules directly (no Prefect server needed)

All `app.*` and `core.*` modules work without Prefect. Secrets fall back to
`.env` when the Prefect server is unreachable:

```bash
# Test matching a batch of jobs
python -c "
from app.matcher import batch_match_jobs
decisions = batch_match_jobs(
    user_id='ff0465b9-...',
    limit=5,
    model='openai/gpt-oss-120b:free',
    provider='openrouter',
)
print(f'Matched: {sum(1 for d in decisions if d[\"status\"]==\"matched\")}/{len(decisions)}')
"

# Test generation for a specific job
python -c "
from app.orchestrator import process_job_for_user
docs = process_job_for_user(
    user_id='ff0465b9-...',
    job_id=123,
    provider='gemini',
    model='models/gemini-3.1-flash-lite',
)
"

# Test scrapers
python -m scrapers.unified_scraper
```

### Override models per run via CLI

```bash
prefect deployment run 'pull-and-process-jobs/job-pipeline' \
  -p '{"match_provider": "gemini", "match_model": "gemini-2.0-flash"}'
```

## Typst (PDF rendering)

`rendercv[full]` requires the **Typst binary**, not the pip package.

1. Download `typst-x86_64-pc-windows-msvc.zip` from
   https://github.com/typst/typst/releases
2. Extract `typst.exe` somewhere permanent (e.g. `C:\tools\`)
3. Add that folder to your system PATH
4. Verify: `typst --version`

## Known gotchas

### `conda run` fails ("file not found")
Use the full Python path instead:
```
& "C:\Users\mmash\.conda\envs\prefect_env\python.exe" -m prefect server start
```

### `prefect secret set` doesn't exist
Prefect 3 removed the `secret` CLI. Use `setup_blocks.py` instead.

### `Starlette` dependency hell
Prefect 3.7.4 requires `starlette>=1.0.1` per its metadata, but actually
works with `starlette 0.38.6`. Pinning `fastapi<0.115.0` forces the
correct Starlette version. Ignore pip's dependency warnings.

### `rendercv` exits 1 on Windows
rendercv prints a `✓` character that crashes on Windows CP1252 console.
The PDF is still generated. The code handles this by checking PDF
existence instead of relying on the exit code.

### Prefect Secret block stores wrong value
Ensure the value is just the URI, not `KEY=value`. If you pasted the
`.env` line by mistake, the prefix `DB_CONN_URI=` will be stored.
Fix:
```python
from prefect.blocks.system import Secret
v = Secret.load('app-config-db-conn-uri').get()
clean = v.removeprefix('DB_CONN_URI=')
Secret(value=clean).save(name='app-config-db-conn-uri', overwrite=True)
```

## After code changes

Only Terminal 2 (deployment runner) needs restarting:

```
Ctrl+C, then:
python -m prefect_flows.deployment
```

The scheduled run uses the `parameters` from the deployment definition
(currently set in `deployment.py`). To change defaults, edit
`deployment.py` and restart the runner.
