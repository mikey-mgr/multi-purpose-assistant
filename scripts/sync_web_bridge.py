"""Copy jobs, matches, and generated documents from the legacy app DB into the web DB."""

import os
import time
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def env(name: str, required: bool = True) -> str | None:
    value = os.getenv(name)
    if required and not value:
        raise SystemExit(f"{name} is required")
    return value


def chunks(rows: list[dict], size: int = 25):
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def run_batch(engine, sql, batch, label: str) -> None:
    for attempt in range(1, 7):
        try:
            with engine.begin() as conn:
                conn.execute(sql, batch)
            return
        except OperationalError:
            if attempt == 6:
                raise
            print(f"{label}: retrying after dropped connection ({attempt})", flush=True)
            engine.dispose()
            time.sleep(min(30, 5 * attempt))


JOBS_SQL = text(
    """insert into jobs
         (id, source, source_url, title, company, location, description,
          job_type, compensation, date_posted, expires, category, remote,
          apply_instructions, scraped_at)
       values
         (:id, :source, :source_url, :title, :company, :location, :description,
          :job_type, :compensation, :date_posted, :expires, :category, :remote,
          :apply_instructions, :scraped_at)
       on conflict (id) do update set
         source = excluded.source,
         source_url = excluded.source_url,
         title = excluded.title,
         company = excluded.company,
         location = excluded.location,
         description = excluded.description,
         job_type = excluded.job_type,
         compensation = excluded.compensation,
         date_posted = excluded.date_posted,
         expires = excluded.expires,
         category = excluded.category,
         remote = excluded.remote,
         apply_instructions = excluded.apply_instructions,
         scraped_at = excluded.scraped_at"""
)

MATCHES_SQL = text(
    """insert into job_matches
         (id, job_id, user_id, status, score, reason, proceed, apply_action,
          apply_recipient, apply_subject, apply_body, apply_url, required_docs,
          expiry_date, merged_pdf, matched_by, created_at)
       values
         (:id, :job_id, :user_id, :status, :score, :reason, :proceed, :apply_action,
          :apply_recipient, :apply_subject, :apply_body, :apply_url, :required_docs,
          :expiry_date, :merged_pdf, :matched_by, :created_at)
       on conflict (job_id, user_id) do update set
         status = excluded.status,
         score = excluded.score,
         reason = excluded.reason,
         proceed = excluded.proceed,
         apply_action = excluded.apply_action,
         apply_recipient = excluded.apply_recipient,
         apply_subject = excluded.apply_subject,
         apply_body = excluded.apply_body,
         apply_url = excluded.apply_url,
         required_docs = excluded.required_docs,
         expiry_date = excluded.expiry_date,
         merged_pdf = excluded.merged_pdf,
         matched_by = excluded.matched_by"""
)

DOCS_SQL = text(
    """insert into documents
         (id, user_id, job_id, document_type, rendercv_yaml, content,
          pdf_path, docx_path, prompt_name, model, tokens_used, created_at)
       values
         (:id, :user_id, :job_id, :document_type, :rendercv_yaml, :content,
          :pdf_path, :docx_path, :prompt_name, :model, :tokens_used, :created_at)
       on conflict (id) do update set
         user_id = excluded.user_id,
         job_id = excluded.job_id,
         document_type = excluded.document_type,
         rendercv_yaml = excluded.rendercv_yaml,
         content = excluded.content,
         pdf_path = excluded.pdf_path,
         docx_path = excluded.docx_path,
         prompt_name = excluded.prompt_name,
         model = excluded.model,
         tokens_used = excluded.tokens_used"""
)


def main() -> None:
    source_uri = env("SOURCE_DB_URI")
    target_uri = env("TARGET_DB_URI")
    target_email = env("TARGET_USER_EMAIL", required=False)
    legacy_email = env("LEGACY_USER_EMAIL", required=False)
    match_limit = int(os.getenv("MATCH_LIMIT", "0") or "0")
    doc_limit = int(os.getenv("DOC_LIMIT", "0") or "0")

    source = create_engine(
        source_uri, connect_args={"connect_timeout": 15}, pool_pre_ping=True
    )
    target_args = {"connect_timeout": 15}
    if os.getenv("TARGET_HOSTADDR"):
        target_args["hostaddr"] = os.getenv("TARGET_HOSTADDR")
    target = create_engine(
        target_uri, connect_args=target_args, pool_pre_ping=True
    )

    with source.connect() as src:
        with target.begin() as dst:
            if target_email:
                user_row = dst.execute(
                    text('select id, email from "user" where lower(email) = lower(:email)'),
                    {"email": target_email},
                ).first()
            else:
                user_row = dst.execute(
                    text('select id, email from "user" order by created_at limit 1')
                ).first()

            if not user_row:
                raise SystemExit(
                    "No target web user found. Set TARGET_USER_EMAIL to an existing account."
                )

            web_user_id = user_row[0]

            if legacy_email:
                legacy_row = src.execute(
                    text("select id from users where lower(email) = lower(:email)"),
                    {"email": legacy_email},
                ).first()
            else:
                legacy_row = src.execute(
                    text("select id from users order by created_at limit 1")
                ).first()

            if not legacy_row:
                raise SystemExit("No legacy user found.")

            legacy_user_id = str(legacy_row[0])
            legacy_uuid = uuid.UUID(legacy_user_id)

            dst.execute(
                text(
                    """insert into profiles (user_id, legacy_user_id, updated_at)
                       values (:user_id, :legacy_user_id, now())
                       on conflict (user_id) do update set
                         legacy_user_id = excluded.legacy_user_id,
                         updated_at = now()"""
                ),
                {"legacy_user_id": legacy_user_id, "user_id": web_user_id},
            )

            existing_job_ids = {
                row[0] for row in dst.execute(text("select id from jobs"))
            }
            existing_match_jobs = {
                row[0]
                for row in dst.execute(
                    text("select job_id from job_matches where user_id = :user_id"),
                    {"user_id": web_user_id},
                )
            }
            existing_doc_ids = {
                str(row[0])
                for row in dst.execute(
                    text("select id from documents where user_id = :user_id"),
                    {"user_id": web_user_id},
                )
            }
            print(
                f"existing matches={len(existing_match_jobs)} documents={len(existing_doc_ids)}",
                flush=True,
            )

        jobs = (
            []
            if os.getenv("SKIP_JOBS") == "1"
            else src.execute(
                text(
                    """select id, site, title, company, job_url, location, description, job_type,
                              compensation, date_posted, expires, category, remote, scraped_at,
                              apply_instructions
                       from scraped_jobs"""
                )
            ).mappings().all()
        )

        job_params = [
            {
                "id": row["id"],
                "source": row["site"],
                "source_url": row["job_url"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "description": row["description"],
                "job_type": row["job_type"],
                "compensation": row["compensation"],
                "date_posted": row["date_posted"],
                "expires": row["expires"],
                "category": row["category"],
                "remote": row["remote"],
                "apply_instructions": row["apply_instructions"],
                "scraped_at": row["scraped_at"],
            }
            for row in jobs
        ]
        if os.getenv("FORCE_JOBS") != "1":
            job_params = [item for item in job_params if item["id"] not in existing_job_ids]
        print(f"pending jobs={len(job_params)}", flush=True)

        for index, batch in enumerate(chunks(job_params), 1):
            run_batch(target, JOBS_SQL, batch, "jobs")
            if index % 20 == 0:
                print(f"jobs batch {index}", flush=True)
        print(f"synced jobs={len(job_params)}", flush=True)

        print("querying matches...", flush=True)
        matches = (
            []
            if os.getenv("SKIP_MATCHES") == "1"
            else src.execute(
                text(
                    """select id, job_id, status, score, reason, matched_by, created_at,
                              apply_action, apply_recipient, apply_subject, apply_body,
                              apply_url, required_docs, proceed, expiry_date, merged_pdf
                       from job_matches
                       where user_id = :user_id
                       order by created_at
                       limit :limit"""
                ),
                {"user_id": legacy_uuid, "limit": match_limit or 1_000_000},
            ).mappings().all()
        )

        match_params = [
            {
                "id": str(row["id"]),
                "job_id": row["job_id"],
                "user_id": web_user_id,
                "status": row["status"],
                "score": row["score"],
                "reason": row["reason"],
                "proceed": row["proceed"],
                "apply_action": row["apply_action"],
                "apply_recipient": row["apply_recipient"],
                "apply_subject": row["apply_subject"],
                "apply_body": row["apply_body"],
                "apply_url": row["apply_url"],
                "required_docs": row["required_docs"],
                "expiry_date": row["expiry_date"],
                "merged_pdf": row["merged_pdf"],
                "matched_by": row["matched_by"],
                "created_at": row["created_at"],
            }
            for row in matches
        ]
        if os.getenv("FORCE_MATCHES") != "1":
            match_params = [
                item for item in match_params if item["job_id"] not in existing_match_jobs
            ]
        print(f"pending matches={len(match_params)}", flush=True)

        for index, batch in enumerate(chunks(match_params), 1):
            run_batch(target, MATCHES_SQL, batch, "matches")
            if index % 20 == 0:
                print(f"matches batch {index}", flush=True)
        print(f"synced matches={len(match_params)}", flush=True)

        print("querying documents...", flush=True)
        documents = src.execute(
            text(
                """select id, job_id, document_type, rendercv_yaml, content, pdf_path,
                          docx_path, prompt_name, model, tokens_used, created_at
                   from generated_documents
                   where resume_id in (select id from resumes where user_id = :user_id)
                      or job_id in (select job_id from job_matches where user_id = :user_id)
                   order by created_at
                   limit :limit"""
            ),
            {"user_id": legacy_uuid, "limit": doc_limit or 1_000_000},
        ).mappings().all()

        doc_params = [
            {
                "id": str(row["id"]),
                "user_id": web_user_id,
                "job_id": row["job_id"],
                "document_type": row["document_type"],
                "rendercv_yaml": row["rendercv_yaml"],
                "content": row["content"],
                "pdf_path": row["pdf_path"],
                "docx_path": row["docx_path"],
                "prompt_name": row["prompt_name"],
                "model": row["model"],
                "tokens_used": row["tokens_used"],
                "created_at": row["created_at"],
            }
            for row in documents
        ]
        if os.getenv("FORCE_DOCS") != "1":
            doc_params = [item for item in doc_params if item["id"] not in existing_doc_ids]
        print(f"pending documents={len(doc_params)}", flush=True)

        for index, batch in enumerate(chunks(doc_params), 1):
            run_batch(target, DOCS_SQL, batch, "documents")
            if index % 20 == 0:
                print(f"documents batch {index}", flush=True)
        print(f"synced documents={len(doc_params)}", flush=True)


if __name__ == "__main__":
    main()
