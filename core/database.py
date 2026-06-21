import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Date, DateTime, Boolean,
    ARRAY, ForeignKey, text, Index, select, Numeric, func, and_,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from pgvector.sqlalchemy import Vector

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DB_CONN_URI,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=Africa/Harare"},
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ── Users / Candidates ────────────────────────────────────────────────

class User(Base):
    __tablename__ = 'users'

    id               = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    first_name       = Column(String(100), nullable=False)
    last_name        = Column(String(100), nullable=False)
    email            = Column(String(255), unique=True, nullable=False)
    phone_1          = Column(String(20))
    phone_2          = Column(String(20))
    linkedin_url     = Column(String(255))
    location_city    = Column(String(100))
    location_country = Column(String(100))
    created_at       = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))

    resumes = relationship('Resume', back_populates='user', cascade='all, delete-orphan')


# ── Resume Versions ───────────────────────────────────────────────────

class Resume(Base):
    __tablename__ = 'resumes'

    id                  = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    user_id             = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    version_name        = Column(String(100), nullable=False)
    professional_summary = Column(Text, nullable=False)
    summary_embedding   = Column(Vector(1536))
    is_active           = Column(Boolean, default=False)
    created_at          = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))
    updated_at          = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))

    user         = relationship('User', back_populates='resumes')
    experiences  = relationship('WorkExperience', back_populates='resume', cascade='all, delete-orphan')
    projects     = relationship('Project', back_populates='resume', cascade='all, delete-orphan')
    education    = relationship('Education', back_populates='resume', cascade='all, delete-orphan')
    certifications = relationship('Certification', back_populates='resume', cascade='all, delete-orphan')
    skills       = relationship('Skill', back_populates='resume', cascade='all, delete-orphan')


# ── Work Experience ───────────────────────────────────────────────────

class WorkExperience(Base):
    __tablename__ = 'work_experience'

    id                  = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    resume_id           = Column(UUID(as_uuid=True), ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False)
    company_name        = Column(String(150), nullable=False)
    job_title           = Column(String(150), nullable=False)
    location            = Column(String(100))
    start_date          = Column(Date, nullable=False)
    end_date            = Column(Date)
    bullet_points       = Column(ARRAY(Text), nullable=False)
    experience_embedding = Column(Vector(1536))
    display_order       = Column(Integer)

    resume = relationship('Resume', back_populates='experiences')


# ── Projects ──────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = 'projects'

    id                = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    resume_id         = Column(UUID(as_uuid=True), ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False)
    project_name      = Column(String(150), nullable=False)
    description       = Column(Text, nullable=False)
    tech_stack        = Column(ARRAY(String(50)))
    project_url       = Column(String(255))
    bullet_points     = Column(ARRAY(Text))
    project_embedding = Column(Vector(1536))
    display_order     = Column(Integer)

    resume = relationship('Resume', back_populates='projects')


# ── Education ─────────────────────────────────────────────────────────

class Education(Base):
    __tablename__ = 'education'

    id              = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    resume_id       = Column(UUID(as_uuid=True), ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False)
    institution_name = Column(String(150), nullable=False)
    degree_type     = Column(String(50), nullable=False)
    field_of_study  = Column(String(100), nullable=False)
    start_date      = Column(Date)
    end_date        = Column(Date)
    grade_or_class  = Column(String(50))
    display_order   = Column(Integer)
    document_path   = Column(Text)  # path to file in data/education/

    resume = relationship('Resume', back_populates='education')


# ── Certifications ────────────────────────────────────────────────────

class Certification(Base):
    __tablename__ = 'certifications'

    id                  = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    resume_id           = Column(UUID(as_uuid=True), ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False)
    cert_name           = Column(String(150), nullable=False)
    issuing_organization = Column(String(150), nullable=False)
    issue_date          = Column(Date)
    credential_url      = Column(Text)
    document_path       = Column(Text)  # path to file in data/certifications/

    resume = relationship('Resume', back_populates='certifications')


# ── Skills ────────────────────────────────────────────────────────────

class Skill(Base):
    __tablename__ = 'skills'

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    resume_id  = Column(UUID(as_uuid=True), ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False)
    skill_name = Column(String(100), nullable=False)
    skill_type = Column(String(50), nullable=False)  # 'Hard Skill', 'Soft Skill', 'Tool'

    resume = relationship('Resume', back_populates='skills')


# ── System Prompts ─────────────────────────────────────────────────────

class Prompt(Base):
    __tablename__ = 'prompts'

    id                  = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name                = Column(String(100), unique=True, nullable=False)
    description         = Column(Text)
    system_prompt       = Column(Text, nullable=False)
    user_prompt_template = Column(Text)
    prompt_type         = Column(String(50), nullable=False)
    model               = Column(String(100), default='gpt-4')
    temperature         = Column(Numeric(3, 2), default=0.7)
    max_tokens          = Column(Integer, default=2048)
    variables           = Column(ARRAY(Text))
    is_active           = Column(Boolean, default=True)
    version             = Column(Integer, default=1)
    created_at          = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))
    updated_at          = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))


# ── Scraped Job Postings ──────────────────────────────────────────────

class ScrapedJob(Base):
    __tablename__ = 'scraped_jobs'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    site         = Column(String(50), nullable=False)
    title        = Column(Text)
    company      = Column(Text)
    job_url      = Column(Text, unique=True)
    location     = Column(Text)
    description  = Column(Text)
    job_type     = Column(Text)
    compensation = Column(Text)
    date_posted  = Column(Date)
    expires      = Column(Date)
    category     = Column(Text)
    remote       = Column(Text)
    job_embedding = Column(Vector(1536))
    search_vector = Column(TSVECTOR)
    scraped_at         = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))
    apply_instructions = Column(Text)


# ── Job Matches ────────────────────────────────────────────────────────

class JobMatch(Base):
    __tablename__ = 'job_matches'

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    job_id     = Column(Integer, ForeignKey('scraped_jobs.id', ondelete='CASCADE'), nullable=False)
    user_id    = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    status     = Column(String(20), nullable=False)   # 'matched' | 'rejected' | 'generated' | 'applied'
    score      = Column(Integer)                       # 0–100
    reason     = Column(Text)                          # comprehensive analysis of gaps (overwritten by 03)
    matched_by = Column(String(20), default='llm')    # 'llm' | 'keyword_fallback'
    llm_raw    = Column(Text)

    # Apply details — populated by 03 (ats_and_cover_v1)
    apply_action      = Column(String(20))   # 'email' | 'external_link' | 'unknown'
    apply_recipient   = Column(Text)         # email address (null if external_link)
    apply_subject     = Column(Text)         # email subject (null if external_link)
    apply_body        = Column(Text)         # email body (null if external_link)
    apply_url         = Column(Text)         # external apply URL (null if email)
    required_docs     = Column(Text)         # JSON array string e.g. '["resume","cover_letter"]'
    proceed           = Column(String(20))   # 'apply_now' | 'needs_docs' | 'needs_info'

    created_at = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))

    __table_args__ = (UniqueConstraint('job_id', 'user_id'),)

    scraped_job = relationship('ScrapedJob')


# ── Generated Documents ────────────────────────────────────────────────

class GeneratedDocument(Base):
    __tablename__ = 'generated_documents'

    id            = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    resume_id     = Column(UUID(as_uuid=True), ForeignKey('resumes.id', ondelete='CASCADE'))
    job_id        = Column(Integer, ForeignKey('scraped_jobs.id', ondelete='SET NULL'))
    document_type = Column(String(50), nullable=False)
    rendercv_yaml = Column(Text)
    content       = Column(Text)
    pdf_path      = Column(Text)
    docx_path     = Column(Text)
    prompt_name   = Column(String(100))
    model         = Column(String(100))
    tokens_used   = Column(Integer, default=0)
    created_at    = Column(DateTime(timezone=True), server_default=text("timezone('Africa/Harare', CURRENT_TIMESTAMP)"))


def save_generated_document(session, **kwargs) -> GeneratedDocument:
    """Insert a row into generated_documents and return it."""
    doc = GeneratedDocument(**kwargs)
    session.add(doc)
    session.flush()
    return doc


# ── Initialisation ────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist (including the RAG view via raw SQL)."""
    Base.metadata.create_all(engine)
    _create_rag_view()
    logger.info("Database tables and RAG view initialised.")


def _create_rag_view():
    """Create or replace the rag_resume_snapshots view."""
    view_sql = """
    CREATE OR REPLACE VIEW rag_resume_snapshots AS
    SELECT
        r.id AS resume_id,
        r.user_id,
        r.version_name,
        r.professional_summary,
        r.summary_embedding,
        CONCAT(
            'Summary: ', r.professional_summary, ' \\n ',
            'Skills: ', COALESCE((SELECT string_agg(skill_name, ', ') FROM skills WHERE resume_id = r.id), ''), ' \\n ',
            'Experience: ', COALESCE((SELECT string_agg(CONCAT(job_title, ' at ', company_name), '; ') FROM work_experience WHERE resume_id = r.id), '')
        ) AS full_metadata_text
    FROM resumes r;
    """
    with engine.connect() as conn:
        conn.execute(text(view_sql))
        conn.commit()


def get_session():
    return SessionLocal()


# ── Vector Search Helpers ──────────────────────────────────────────────

def search_projects(embedding_vector, user_id=None, resume_id=None, top_k=5):
    """
    Semantic (cosine similarity) search across projects.
    Filter by user_id or resume_id for strict metadata scoping.
    """
    session = get_session()
    try:
        stmt = select(
            Project,
            Project.project_embedding.cosine_distance(embedding_vector).label('distance')
        ).order_by(Project.project_embedding.cosine_distance(embedding_vector))

        if user_id is not None:
            stmt = stmt.join(Resume).filter(Resume.user_id == user_id)
        if resume_id is not None:
            stmt = stmt.filter(Project.resume_id == resume_id)

        results = session.execute(stmt.limit(top_k)).all()
        return [(row.Project, row.distance) for row in results]
    finally:
        session.close()


def search_experiences(embedding_vector, user_id=None, resume_id=None, top_k=5):
    """
    Semantic (cosine similarity) search across work experiences.
    Filter by user_id or resume_id for strict metadata scoping.
    """
    session = get_session()
    try:
        stmt = select(
            WorkExperience,
            WorkExperience.experience_embedding.cosine_distance(embedding_vector).label('distance')
        ).order_by(WorkExperience.experience_embedding.cosine_distance(embedding_vector))

        if user_id is not None:
            stmt = stmt.join(Resume).filter(Resume.user_id == user_id)
        if resume_id is not None:
            stmt = stmt.filter(WorkExperience.resume_id == resume_id)

        results = session.execute(stmt.limit(top_k)).all()
        return [(row.WorkExperience, row.distance) for row in results]
    finally:
        session.close()


def search_resumes(embedding_vector, user_id=None, is_active=None, top_k=5):
    """
    Semantic search across resume summaries.
    Metadata filters: user_id, is_active.
    """
    session = get_session()
    try:
        stmt = select(
            Resume,
            Resume.summary_embedding.cosine_distance(embedding_vector).label('distance')
        ).order_by(Resume.summary_embedding.cosine_distance(embedding_vector))

        if user_id is not None:
            stmt = stmt.filter(Resume.user_id == user_id)
        if is_active is not None:
            stmt = stmt.filter(Resume.is_active == is_active)

        results = session.execute(stmt.limit(top_k)).all()
        return [(row.Resume, row.distance) for row in results]
    finally:
        session.close()


# ── Hybrid Search on scraped_jobs (keyword + semantic) ─────────────────

def search_jobs_hybrid(query_text, embedding_vector=None, site=None, top_k=10):
    """
    Hybrid search across scraped_jobs:
    - Full-text keyword match (tsvector) weighted 0.5
    - Semantic (cosine similarity) on job_embedding weighted 0.5 (if available)
    Falls back to pure full-text if no embedding_vector provided.
    """
    session = get_session()
    try:
        tsq = func.plainto_tsquery('english', query_text)
        ts_rank = func.ts_rank(ScrapedJob.search_vector, tsq)

        if embedding_vector is not None:
            cosine_dist = ScrapedJob.job_embedding.cosine_distance(embedding_vector)
            combined = (ts_rank * 0.5 + (1 - cosine_dist) * 0.5).label('score')
            stmt = select(ScrapedJob, combined).filter(
                ScrapedJob.search_vector.op('@@')(tsq)
            )
            if ScrapedJob.job_embedding.isnot(None):
                stmt = stmt.filter(ScrapedJob.job_embedding.isnot(None))
        else:
            stmt = select(ScrapedJob, ts_rank.label('score')).filter(
                ScrapedJob.search_vector.op('@@')(tsq)
            )

        if site:
            stmt = stmt.filter(ScrapedJob.site == site)

        stmt = stmt.order_by(text('score DESC')).limit(top_k)
        results = session.execute(stmt).all()
        return [(row.ScrapedJob, row.score) for row in results]
    finally:
        session.close()


def get_unprocessed_jobs(limit=50):
    """Fetch jobs not yet linked to a generated document (simple LIMIT scan)."""
    session = get_session()
    try:
        return session.query(ScrapedJob).limit(limit).all()
    finally:
        session.close()


def get_unscored_jobs(user_id: str, limit: int = 50):
    """Fetch jobs not yet in job_matches for this user."""
    session = get_session()
    try:
        subq = session.query(JobMatch.job_id).filter(JobMatch.user_id == user_id)
        return session.query(ScrapedJob).filter(
            ~ScrapedJob.id.in_(subq)
        ).limit(limit).all()
    finally:
        session.close()


def get_matched_unprocessed_jobs(user_id: str, limit: int = 10):
    """
    Fetch matched jobs that don't have a generated resume for the user's active resume yet.
    """
    session = get_session()
    try:
        # Find user's active resume
        resume = session.query(Resume).filter(
            Resume.user_id == user_id,
            Resume.is_active == True,
        ).first()
        if not resume:
            logger.warning("No active resume for user %s", user_id)
            return []

        matched_ids = session.query(JobMatch.job_id).filter(
            JobMatch.user_id == user_id,
            JobMatch.status == 'matched',
        )
        generated_ids = session.query(GeneratedDocument.job_id).filter(
            GeneratedDocument.document_type == 'resume',
            GeneratedDocument.resume_id == resume.id,
        )
        return session.query(ScrapedJob).filter(
            ScrapedJob.id.in_(matched_ids),
            ~ScrapedJob.id.in_(generated_ids),
        ).limit(limit).all()
    finally:
        session.close()


def get_generated_unapplied_jobs(user_id: str, limit: int = 10):
    """
    Fetch jobs that have documents generated but haven't been applied to yet.
    """
    session = get_session()
    try:
        return session.query(ScrapedJob).join(JobMatch, ScrapedJob.id == JobMatch.job_id).filter(
            JobMatch.user_id == user_id,
            JobMatch.status == 'generated',
        ).limit(limit).all()
    finally:
        session.close()


def get_generated_jobs_with_matches(user_id: str, limit: int = 10):
    """
    Fetch generated-but-unapplied jobs with their match score and reason.
    Returns list of dicts with job data and match_data.
    """
    session = get_session()
    try:
        rows = session.query(ScrapedJob, JobMatch).join(JobMatch, ScrapedJob.id == JobMatch.job_id).filter(
            JobMatch.user_id == user_id,
            JobMatch.status == 'generated',
        ).limit(limit).all()
        return [
            {
                "job": job,
                "match": match,
            }
            for job, match in rows
        ]
    finally:
        session.close()


def bulk_insert_job_matches(matches: list[dict]):
    """Insert multiple JobMatch rows (batch result from LLM)."""
    session = get_session()
    try:
        for m in matches:
            session.add(JobMatch(**m))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_job_match_status(job_id: int, user_id: str, status: str) -> bool:
    """Update the status of a JobMatch row (e.g. 'matched' → 'applied')."""
    session = get_session()
    try:
        row = session.query(JobMatch).filter(
            JobMatch.job_id == job_id,
            JobMatch.user_id == user_id,
        ).first()
        if row:
            row.status = status
            session.commit()
            return True
        logger.warning("No JobMatch found for job %s / user %s", job_id, user_id)
        return False
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_apply_details(
    job_id: int,
    user_id: str,
    apply_action: str | None = None,
    apply_recipient: str | None = None,
    apply_subject: str | None = None,
    apply_body: str | None = None,
    apply_url: str | None = None,
    required_docs: list[str] | None = None,
    reason: str | None = None,
    proceed: str | None = None,
) -> bool:
    """Save apply details and updated reason to a JobMatch row."""
    session = get_session()
    try:
        row = session.query(JobMatch).filter(
            JobMatch.job_id == job_id,
            JobMatch.user_id == user_id,
        ).first()
        if not row:
            logger.warning("No JobMatch found for job %s / user %s", job_id, user_id)
            return False

        if apply_action is not None:
            row.apply_action = apply_action
        if apply_recipient is not None:
            row.apply_recipient = apply_recipient
        if apply_subject is not None:
            row.apply_subject = apply_subject
        if apply_body is not None:
            row.apply_body = apply_body
        if apply_url is not None:
            row.apply_url = apply_url
        if required_docs is not None:
            row.required_docs = json.dumps(required_docs)
        if reason is not None:
            row.reason = reason
        if proceed is not None:
            row.proceed = proceed

        row.status = 'generated'
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_application_documents(resume_id: str, job_id: int) -> dict:
    """
    Collect all available document paths for a resume + job combo.

    Returns dict with keys: 'resume_pdf', 'resume_docx', 'cover_letter_docx',
    'education_docs' (list), 'certification_docs' (list).
    """
    session = get_session()
    try:
        rid = uuid.UUID(resume_id) if isinstance(resume_id, str) else resume_id

        # Generated documents for this resume + job
        gen = session.query(GeneratedDocument).filter(
            GeneratedDocument.resume_id == rid,
            GeneratedDocument.job_id == job_id,
        ).all()

        result = {
            "resume_pdf": None,
            "resume_docx": None,
            "cover_letter_docx": None,
            "education_docs": [],
            "certification_docs": [],
        }

        for doc in gen:
            if doc.document_type == "resume":
                if doc.pdf_path and not result["resume_pdf"]:
                    result["resume_pdf"] = doc.pdf_path
            elif doc.document_type == "cover_letter":
                if doc.docx_path and not result["cover_letter_docx"]:
                    result["cover_letter_docx"] = doc.docx_path

        # Static document paths from education + certifications tables
        edu_rows = session.query(Education).filter(Education.resume_id == rid).all()
        for e in edu_rows:
            if e.document_path:
                result["education_docs"].append(e.document_path)

        cert_rows = session.query(Certification).filter(Certification.resume_id == rid).all()
        for c in cert_rows:
            if c.document_path:
                result["certification_docs"].append(c.document_path)

        return result
    except Exception:
        logger.warning("Error collecting application documents for resume %s / job %s", resume_id, job_id, exc_info=True)
        return {}
    finally:
        session.close()


# ── Prompt Helpers ─────────────────────────────────────────────────────

def get_active_prompt(prompt_name):
    """Fetch the active version of a prompt by name."""
    session = get_session()
    try:
        return session.query(Prompt).filter(
            Prompt.name == prompt_name,
            Prompt.is_active == True
        ).first()
    finally:
        session.close()


def build_prompt(prompt_name, **variables):
    """
    Load a prompt template and substitute variables.
    Returns (system_prompt, user_prompt) tuple.
    """
    prompt = get_active_prompt(prompt_name)
    if not prompt:
        raise ValueError(f"No active prompt found: {prompt_name}")

    system = prompt.system_prompt
    user_template = prompt.user_prompt_template or ""

    for key, val in variables.items():
        placeholder = "{{" + key + "}}"
        system = system.replace(placeholder, str(val))
        user_template = user_template.replace(placeholder, str(val))

    return system, user_template, prompt


# ── Helpers for scraped_jobs ────────────────────────────────────────

def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def get_existing_job_urls() -> set[str]:
    """Return all job_url values currently in scraped_jobs (for skip logic)."""
    session = get_session()
    try:
        rows = session.query(ScrapedJob.job_url).all()
        return {r[0] for r in rows if r[0]}
    finally:
        session.close()


def insert_jobs(jobs_list):
    """Insert a list of job dicts into scraped_jobs. Skips duplicates by job_url."""
    if not jobs_list:
        return 0

    session = get_session()
    count = 0
    try:
        for job in jobs_list:
            url = job.get('job_url')
            if url:
                existing = session.query(ScrapedJob).filter(
                    ScrapedJob.job_url == url
                ).first()
                if existing:
                    continue

            db_job = ScrapedJob(
                site=job.get('site'),
                title=job.get('title'),
                company=job.get('company'),
                job_url=job.get('job_url'),
                location=job.get('location'),
                description=job.get('description'),
                job_type=job.get('job_type'),
                compensation=job.get('compensation'),
                date_posted=_parse_date(job.get('date_posted')),
                expires=_parse_date(job.get('expires')),
                category=job.get('category'),
                remote=job.get('remote'),
                apply_instructions=job.get('apply_instructions'),
            )
            session.add(db_job)
            count += 1

        session.commit()
        logger.info("Inserted %d new job(s) into database.", count)
    except Exception as e:
        session.rollback()
        logger.error("Database insert failed: %s", e)
        raise
    finally:
        session.close()

    return count
