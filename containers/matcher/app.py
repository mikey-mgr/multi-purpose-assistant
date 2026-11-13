"""Mukana matching and cover-letter worker.

Runs inside a Cloudflare Container. The Worker injects the Neon connection
string and Gemini key as request headers; this service never persists them.
"""

import io
import json
import logging
import os
import secrets
import time
from typing import Any

import httpx
import psycopg
from docx import Document
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader

app = FastAPI(title="Mukana Matcher", version="0.1.0")

GEMINI_BASE = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_JOBS = int(os.getenv("MAX_MATCH_JOBS", "50"))
MAX_GENERATE = int(os.getenv("MAX_GENERATE_JOBS", "5"))

logger = logging.getLogger("mukana.matcher")


class MatchRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=100)
    web_user_id: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=50, ge=1, le=100)
    # Restrict this run to specific jobs (used when a user forwards a JD on
    # WhatsApp, so only they get matched to it).
    job_ids: list[int] | None = Field(default=None, max_length=50)
    match_since: str | None = Field(default=None, max_length=40)


class GenerateRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=100)
    web_user_id: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=5, ge=1, le=10)


def db_connect(url: str):
    return psycopg.connect(url, connect_timeout=15)


def resolve_secrets(
    supplied_secret: str | None,
    database_url: str | None,
    gemini_key: str | None,
) -> tuple[str, str]:
    configured_secret = os.getenv("MATCH_TRIGGER_SECRET")
    if configured_secret and (
        not supplied_secret or not secrets.compare_digest(configured_secret, supplied_secret)
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    resolved_db = database_url or os.getenv("DATABASE_URL")
    resolved_key = gemini_key or os.getenv("GEMINI_API_KEY")
    if not resolved_db or not resolved_key:
        raise HTTPException(status_code=503, detail="Matcher secrets are not configured")
    return resolved_db, resolved_key


def gemini_keys(primary: str) -> list[str]:
    """Every key worth trying, primary first.

    A rate limit (RPM/TPM/RPD) is per key, so the secondary key is used when the
    first is exhausted instead of failing the whole match run.
    """
    candidates = [primary, os.getenv("SECONDARY_GEMINI_API_KEY")]
    seen: list[str] = []
    for candidate in candidates:
        value = (candidate or "").strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def gemini_chat(key: str, messages: list[dict], temperature: float = 0.2) -> tuple[str, int]:
    keys = gemini_keys(key)
    last_error: Exception | None = None

    for key_index, api_key in enumerate(keys):
        for attempt in range(4):
            try:
                response = httpx.post(
                    f"{GEMINI_BASE.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": GEMINI_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 4096,
                    },
                    timeout=120,
                )
                if response.status_code == 429:
                    # This key is rate limited; try the other key immediately
                    # rather than sleeping through the whole backoff on it.
                    raise RuntimeError("Gemini rate limited (429)")
                if response.status_code in {401, 403, 408, 425, 500, 502, 503, 504}:
                    raise RuntimeError(f"Gemini temporary error {response.status_code}")
                if response.status_code == 400:
                    detail = (response.text or "").lower()
                    if any(
                        token in detail
                        for token in ("api key", "api_key", "permission", "quota", "credential", "billing")
                    ):
                        raise RuntimeError("Gemini rejected the API key")
                response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices") or []
                if not choices:
                    raise RuntimeError("Gemini returned no choices")
                content = (choices[0].get("message") or {}).get("content") or ""
                tokens = int((payload.get("usage") or {}).get("total_tokens") or 0)
                return content, tokens
            except Exception as exc:
                last_error = exc
                message = str(exc)
                # Only switch keys when the key looks exhausted. A malformed
                # request would fail identically on the next one.
                key_exhausted = "rate limited" in message or "rejected the API key" in message
                if key_exhausted and key_index + 1 < len(keys):
                    logger.warning("Gemini key %d exhausted; switching to the next key", key_index + 1)
                    break
                if attempt == 3:
                    break
                time.sleep(2 + attempt * 3)

    raise RuntimeError(f"Gemini request failed after retries: {last_error}")


def extract_json(text: str) -> Any:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("No JSON array in model response")
    return json.loads(text[start : end + 1])


def profile_text(profile: dict) -> str:
    resume = (profile.get("resume_text") or "").strip()
    lines = [
        f"Headline: {profile.get('headline') or 'Not provided'}",
        f"Location: {profile.get('location') or 'Not provided'}",
        f"Years of experience: {profile.get('years_experience') or 0}",
        f"Target role families: {', '.join(profile.get('target_families') or []) or 'Not provided'}",
        f"Match mode: {profile.get('match_mode') or 'balanced'}",
    ]
    if resume:
        lines.append("Resume / career summary:")
        lines.append(resume[:12000])
    return "\n".join(lines)


def match_prompt(profile: dict, jobs: list[dict]) -> str:
    mode = profile.get("match_mode") or "balanced"
    thresholds = {"strict": 65, "balanced": 50, "broad": 40}
    threshold = thresholds.get(mode, 50)
    job_blocks = []
    for index, job in enumerate(jobs, 1):
        job_blocks.append(
            "\n".join(
                [
                    f"Job {index}:",
                    f"title: {job.get('title') or ''}",
                    f"company: {job.get('company') or ''}",
                    f"location: {job.get('location') or ''}",
                    f"job_type: {job.get('job_type') or ''}",
                    f"category: {job.get('category') or ''}",
                    f"remote: {job.get('remote') or ''}",
                    f"description: {(job.get('description') or '')[:5000]}",
                ]
            )
        )
    return f"""You are Mukana's job matcher for Zimbabwe and remote roles.
Candidate:
{profile_text(profile)}

Decide whether each job is worth applying for.

## What can reject a candidate (hard gates only)
Only reject when the posting states a requirement the candidate clearly cannot meet:
- work authorisation, or a location the candidate cannot work from
- a licence or registration the candidate does not hold (driver's licence, professional body)
- a named discipline-specific qualification the candidate does not hold (see below)
- more required years of experience than the candidate has, where a number is stated

Nothing else is a rejection reason.

## Field-specific qualifications ARE a gate
A degree requirement is not satisfied by any degree. Read the posting carefully and separate
two different things:

- LEVEL-only barrier: "O Level", "A Level", "a diploma", "a degree", "any degree",
  "a recognised qualification". The candidate meets or exceeds these. Not a gate.
- FIELD barrier: the posting names the discipline it needs, for example
  "Degree in Accounting", "Bachelor's in Finance", "BSc in Computer Science",
  "studying towards a finance/accounting qualification", "Commerce or Business degree".
  A degree from a different discipline does NOT satisfy this. This IS a gate.

When a posting names a required discipline, compare it with the candidate's actual degree fields
and completed coursework. If the candidate's field does not match the named discipline, reject it
and say which discipline was required. Do not treat "has a bachelor's degree" as meeting
"degree in Accounting", "degree in Finance", "degree in Marketing", "degree in Human Resources",
"degree in Law", "degree in Nursing" or similar. Being part-qualified or studying towards it only
counts when the profile states that.

This distinction decides most entry-level graduate and internship roles:
- "Finance Graduate Intern" / "Accounting Graduate Trainee" / "HR Assistant" /
  "Risk Analytics Graduate Trainee" all name a discipline. An IT degree does not satisfy them.
- "Graduate Trainee" with no discipline stated, or "any degree accepted", does satisfy them.

## Target role families are a preference, not a gate
"Target role families" ranks which roles to surface first. It must never reject a job on its own.
A role outside those families is still eligible when the work is entry-level, trainable, or
adjacent to the candidate's demonstrated skills, and no field-specific gate is failed.

## Over-qualification is never a rejection reason
When a posting asks for O Level, A Level, a diploma or "any degree", a candidate holding a
bachelor's degree meets and exceeds the requirement. Never reject because the candidate is
"too qualified" or "over-specialised" when the employer set a low bar. This does not override
the field barrier above: exceeding the level does not supply a missing discipline.

## Scoring
Work down this list and stop at the first band that applies.
1. 85-100: strong fit; meets every stated requirement and has direct evidence for the core work
2. 70-84: credible fit; meets requirements, gaps are transferable
3. 55-69: eligible and sensible; a training, graduate or entry-level role the candidate clearly
   qualifies for, where the work is at least adjacent to their skills
4. 40-54: permitted but weak; meets every stated requirement but the work is unrelated to their
   field (e.g. a low-bar cashier, security or reception role). Include it, score it here.
5. 0-39: reject; one or more hard gates failed, including a field-specific qualification

Never place a low-barrier unrelated role above 54 simply because the candidate out-qualifies it.
Being over-qualified makes a job permissible, not a strong fit.

## Mode "{mode}"
- strict: only high-fit roles inside the target families
- balanced: roles inside the target families plus closely adjacent work
- broad: also include entry-level, trainee and transferable roles the candidate qualifies for even
  when the job family differs. Broad mode widens which roles are acceptable; it does not waive
  a field-specific qualification.

Use the {mode} mode: a role is matched only when score >= {threshold}. Be realistic about
seniority, required qualifications and location/right-to-work. Do not invent experience.
The reason must name the hard gate that failed, or the requirement the candidate exceeds and the
transferable evidence that supports the application. Never write a vague field-mismatch reason.

Return a JSON array with one object per job, in order.
Each object must contain: job_index, status ("matched" or "rejected"), score (0-100), reason (max 400 chars).

Jobs:
{chr(10).join(job_blocks)}"""


def require_secret(supplied: str | None) -> None:
    configured = os.getenv("MATCH_TRIGGER_SECRET")
    if configured and (
        not supplied or not secrets.compare_digest(configured, supplied)
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")


def extract_text(filename: str, data: bytes) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:50])
    if suffix == "docx":
        document = Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    if suffix in {"txt", "md"}:
        return data.decode("utf-8", errors="replace")
    raise HTTPException(status_code=415, detail="Unsupported resume file type")


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    x_match_trigger_secret: str | None = Header(default=None),
):
    require_secret(x_match_trigger_secret)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")
    text = extract_text(file.filename or "", data)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = "\n".join(line for line in text.splitlines() if line.strip())
    if len(text) < 20:
        raise HTTPException(status_code=422, detail="Could not read enough text from the file")
    return {"text": text[:20000], "chars": len(text[:20000])}


@app.get("/health")
def health():
    return {"ok": True, "service": "mukana-matcher"}


@app.post("/match")
def match(
    body: MatchRequest,
    x_database_url: str | None = Header(default=None),
    x_gemini_key: str | None = Header(default=None),
    x_match_trigger_secret: str | None = Header(default=None),
):
    x_database_url, x_gemini_key = resolve_secrets(
        x_match_trigger_secret, x_database_url, x_gemini_key
    )

    user_id = body.web_user_id or body.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    limit = min(body.limit, MAX_JOBS)
    with db_connect(x_database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """select user_id, headline, location, years_experience, target_families,
                          match_mode, resume_text, match_since
                   from profiles where user_id = %s""",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Profile not found")
            profile = {
                "user_id": row[0],
                "headline": row[1],
                "location": row[2],
                "years_experience": row[3],
                "target_families": row[4],
                "match_mode": row[5],
                "resume_text": row[6],
                "match_since": row[7],
            }
            if not profile["headline"] and not profile["resume_text"]:
                raise HTTPException(status_code=400, detail="Profile has no headline or resume text")

            cur.execute(
                """select j.id, j.title, j.company, j.location, j.job_type, j.category,
                          j.remote, j.description, j.source_url
                   from jobs j
                   where (not exists (
                       select 1 from job_matches m
                       where m.job_id = j.id and m.user_id = %s
                   ))
                   and (j.expires is null or j.expires >= current_date)
                   and (
                       %s::timestamptz is null
                       or j.date_posted >= %s::timestamptz::date
                       or j.scraped_at >= %s::timestamptz
                   )
                   and (
                       %s::int[] is null
                       or j.id = any(%s::int[])
                   )
                   and (
                       j.owner_user_id is null
                       or j.owner_user_id = %s
                   )
                   order by j.date_posted desc nulls last, j.id desc
                   limit %s""",
                (
                    user_id,
                    profile["match_since"],
                    profile["match_since"],
                    profile["match_since"],
                    body.job_ids,
                    body.job_ids,
                    user_id,
                    limit,
                ),
            )
            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, item)) for item in cur.fetchall()]

            if not jobs:
                return {"user_id": user_id, "processed": 0, "matched": 0, "rejected": 0}

            content, tokens = gemini_chat(
                x_gemini_key,
                [
                    {"role": "system", "content": "You output strict JSON only."},
                    {"role": "user", "content": match_prompt(profile, jobs)},
                ],
            )
            decisions = extract_json(content)
            threshold = {"strict": 65, "balanced": 50, "broad": 40}.get(
                profile["match_mode"] or "balanced", 50
            )
            matched = 0
            rejected = 0
            for item in decisions if isinstance(decisions, list) else []:
                index = int(item.get("job_index") or 0) - 1
                if index < 0 or index >= len(jobs):
                    continue
                try:
                    score = max(0, min(100, int(item.get("score") or 0)))
                except (TypeError, ValueError):
                    score = 0
                status = "matched" if score >= threshold else "rejected"
                if item.get("status") == "rejected":
                    status = "rejected"
                reason = str(item.get("reason") or "")[:2000]
                cur.execute(
                    """insert into job_matches
                         (job_id, user_id, status, score, reason, matched_by)
                       values (%s, %s, %s, %s, %s, 'container_llm')
                       on conflict (job_id, user_id) do update set
                         status = excluded.status,
                         score = excluded.score,
                         reason = excluded.reason,
                         matched_by = excluded.matched_by""",
                    (jobs[index]["id"], user_id, status, score, reason),
                )
                if status == "matched":
                    matched += 1
                else:
                    rejected += 1
            conn.commit()

    return {
        "user_id": user_id,
        "processed": matched + rejected,
        "matched": matched,
        "rejected": rejected,
        "tokens": tokens,
        "model": GEMINI_MODEL,
    }


@app.post("/generate")
def generate(
    body: GenerateRequest,
    x_database_url: str | None = Header(default=None),
    x_gemini_key: str | None = Header(default=None),
    x_match_trigger_secret: str | None = Header(default=None),
):
    x_database_url, x_gemini_key = resolve_secrets(
        x_match_trigger_secret, x_database_url, x_gemini_key
    )

    user_id = body.web_user_id or body.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    limit = min(body.limit, MAX_GENERATE)
    generated = 0
    tokens_total = 0
    with db_connect(x_database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """select p.headline, p.location, p.years_experience, p.resume_text
                   from profiles p where p.user_id = %s""",
                (user_id,),
            )
            profile_row = cur.fetchone()
            if not profile_row:
                raise HTTPException(status_code=404, detail="Profile not found")

            cur.execute(
                """select m.job_id, j.title, j.company, j.description
                   from job_matches m
                   join jobs j on j.id = m.job_id
                   where m.user_id = %s and m.status = 'matched'
                     and not exists (
                       select 1 from documents d
                       where d.user_id = m.user_id and d.job_id = m.job_id
                         and d.document_type = 'cover_letter'
                     )
                   order by m.score desc nulls last
                   limit %s""",
                (user_id, limit),
            )
            jobs = cur.fetchall()

            for job_id, title, company, description in jobs:
                prompt = f"""Write a concise, specific cover letter for this job.
Candidate headline: {profile_row[0] or 'Not provided'}
Candidate location: {profile_row[1] or 'Not provided'}
Years of experience: {profile_row[2] or 0}
Candidate resume:
{(profile_row[3] or '')[:10000]}

Job title: {title or ''}
Company: {company or ''}
Job description:
{(description or '')[:6000]}

Rules: one page, plain text, no placeholders, no invented experience, direct and professional, Zimbabwe/remote context where relevant. Return only the cover letter."""
                content, tokens = gemini_chat(
                    x_gemini_key,
                    [
                        {"role": "system", "content": "You write honest, tailored application letters."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                )
                tokens_total += tokens
                cur.execute(
                    """insert into documents
                         (user_id, job_id, document_type, content, prompt_name, model, tokens_used)
                       values (%s, %s, 'cover_letter', %s, 'mukana_cover_letter', %s, %s)""",
                    (user_id, job_id, content.strip(), GEMINI_MODEL, tokens),
                )
                generated += 1
            conn.commit()

    return {"user_id": user_id, "generated": generated, "tokens": tokens_total}
