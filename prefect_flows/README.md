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
| 2 | `python -m prefect_flows.deployment` | Registers cron + runs scheduler |
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
- `app-config-openai-api-key`
- `app-config-openrouter-api-key`
- `app-config-gemini-api-key`
- `app-config-serpapi-api-key`
- `app-config-gmail-address`
- `app-config-gmail-app-password`

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

## Manual trigger

```bash
conda activate prefect_env
python -m prefect_flows.job_pipeline --manual <user_id> <job_id>
```

Or via Prefect CLI:
```bash
prefect deployment run 'pull-and-process-jobs/job-pipeline'
```

The scheduled run uses the `parameters` from the deployment definition
(currently set in `deployment.py`). To change the default user_id, edit
`deployment.py` and restart the runner.
