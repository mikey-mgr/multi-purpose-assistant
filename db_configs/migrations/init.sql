-- PostgreSQL initialisation for ai_assistant database
-- Run: psql -U postgres -f init.sql
-- Requires: pgcrypto, pgvector extensions

CREATE DATABASE ai_assistant;

\c ai_assistant;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

ALTER DATABASE ai_assistant SET timezone TO 'Africa/Harare';

-- ── Users / Candidates ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name       VARCHAR(100) NOT NULL,
    last_name        VARCHAR(100) NOT NULL,
    email            VARCHAR(255) UNIQUE NOT NULL,
    phone_1          VARCHAR(20),
    phone_2          VARCHAR(20),
    linkedin_url     VARCHAR(255),
    location_city    VARCHAR(100),
    location_country VARCHAR(100),
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

-- ── Resume Versions ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS resumes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    version_name        VARCHAR(100) NOT NULL,
    professional_summary TEXT NOT NULL,
    summary_embedding   vector(1536),
    is_active           BOOLEAN DEFAULT false,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

-- ── Work Experience ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS work_experience (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id           UUID REFERENCES resumes(id) ON DELETE CASCADE,
    company_name        VARCHAR(150) NOT NULL,
    job_title           VARCHAR(150) NOT NULL,
    location            VARCHAR(100),
    start_date          DATE NOT NULL,
    end_date            DATE,
    bullet_points       TEXT[] NOT NULL,
    experience_embedding vector(1536),
    display_order       INT
);

-- ── Projects ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id           UUID REFERENCES resumes(id) ON DELETE CASCADE,
    project_name        VARCHAR(150) NOT NULL,
    description         TEXT NOT NULL,
    tech_stack          VARCHAR(50)[],
    project_url         VARCHAR(255),
    bullet_points       TEXT[],
    project_embedding   vector(1536),
    display_order       INT
);

-- ── Education & Certifications ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS education (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id       UUID REFERENCES resumes(id) ON DELETE CASCADE,
    institution_name VARCHAR(150) NOT NULL,
    degree_type     VARCHAR(50) NOT NULL,
    field_of_study  VARCHAR(100) NOT NULL,
    start_date      DATE,
    end_date        DATE,
    grade_or_class  VARCHAR(50),
    display_order   INT
);

CREATE TABLE IF NOT EXISTS certifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id           UUID REFERENCES resumes(id) ON DELETE CASCADE,
    cert_name           VARCHAR(150) NOT NULL,
    issuing_organization VARCHAR(150) NOT NULL,
    issue_date          DATE,
    credential_url      TEXT
);

-- ── Skills ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skills (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id  UUID REFERENCES resumes(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    skill_type VARCHAR(50) NOT NULL  -- 'Hard Skill', 'Soft Skill', 'Tool'
);

-- ── System Prompts (versioned, mutation-safe) ────────────────────────

CREATE TABLE IF NOT EXISTS prompts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(100) NOT NULL UNIQUE,
    description         TEXT,
    system_prompt       TEXT NOT NULL,
    user_prompt_template TEXT,
    prompt_type         VARCHAR(50) NOT NULL,  -- 'resume', 'cover_letter', 'skills_analysis', 'interview_prep'
    model               VARCHAR(100) DEFAULT 'gpt-4',
    temperature         NUMERIC(3,2) DEFAULT 0.7,
    max_tokens          INTEGER DEFAULT 2048,
    variables           TEXT[],  -- e.g. {'user_profile', 'job_description'}
    is_active           BOOLEAN DEFAULT true,
    version             INTEGER DEFAULT 1,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

-- ── Scraped Job Postings ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scraped_jobs (
    id              SERIAL PRIMARY KEY,
    site            VARCHAR(50) NOT NULL,
    title           TEXT,
    company         TEXT,
    job_url         TEXT UNIQUE,
    location        TEXT,
    description     TEXT,
    job_type        TEXT,
    compensation    TEXT,
    date_posted     DATE,
    expires         DATE,
    category        TEXT,
    remote          TEXT,
    scraped_at          TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    apply_instructions  TEXT
);

-- Migration: add columns that may not exist in older versions of this table
ALTER TABLE scraped_jobs ADD COLUMN IF NOT EXISTS job_embedding vector(1536);
ALTER TABLE scraped_jobs ADD COLUMN IF NOT EXISTS search_vector tsvector;
ALTER TABLE scraped_jobs ALTER COLUMN scraped_at SET DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP);

-- Populate search_vector for existing & future rows
CREATE OR REPLACE FUNCTION scraped_jobs_search_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        coalesce(NEW.title, '') || ' ' ||
        coalesce(NEW.company, '') || ' ' ||
        coalesce(NEW.description, '') || ' ' ||
        coalesce(NEW.location, '') || ' ' ||
        coalesce(NEW.category, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_scraped_jobs_search ON scraped_jobs;
CREATE TRIGGER trg_scraped_jobs_search
    BEFORE INSERT OR UPDATE OF title, company, description, location, category
    ON scraped_jobs
    FOR EACH ROW
    EXECUTE FUNCTION scraped_jobs_search_update();

-- Backfill search_vector for existing rows
UPDATE scraped_jobs SET search_vector = to_tsvector('english',
    coalesce(title, '') || ' ' ||
    coalesce(company, '') || ' ' ||
    coalesce(description, '') || ' ' ||
    coalesce(location, '') || ' ' ||
    coalesce(category, '')
) WHERE search_vector IS NULL;

CREATE INDEX IF NOT EXISTS idx_scraped_jobs_site          ON scraped_jobs(site);
CREATE INDEX IF NOT EXISTS idx_scraped_jobs_date_posted   ON scraped_jobs(date_posted);
CREATE INDEX IF NOT EXISTS idx_scraped_jobs_scraped_at    ON scraped_jobs(scraped_at);
CREATE INDEX IF NOT EXISTS idx_scraped_jobs_search_vector ON scraped_jobs USING GIN(search_vector);

-- ── Generated Documents (snapshots of what was sent) ────────────────

CREATE TABLE IF NOT EXISTS generated_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id       UUID REFERENCES resumes(id) ON DELETE CASCADE,
    job_id          INTEGER REFERENCES scraped_jobs(id) ON DELETE SET NULL,
    document_type   VARCHAR(50) NOT NULL,  -- 'resume', 'cover_letter', 'skills_analysis'
    rendercv_yaml   TEXT,                  -- full YAML sent to rendercv (resumes only)
    content         TEXT,                  -- raw LLM output / cover letter text
    pdf_path        TEXT,                  -- path to generated PDF
    docx_path       TEXT,                  -- path to generated DOCX (cover letters)
    prompt_name     VARCHAR(100),          -- which prompt version was used
    model           VARCHAR(100),
    tokens_used     INTEGER DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

-- ── Job Matches (decoupled from generated_documents) ─────────────────

CREATE TABLE IF NOT EXISTS job_matches (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id     INTEGER NOT NULL REFERENCES scraped_jobs(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status     VARCHAR(20) NOT NULL CHECK (status IN ('matched', 'rejected')),
    score      INTEGER CHECK (score >= 0 AND score <= 100),
    reason     TEXT,
    matched_by VARCHAR(20) DEFAULT 'llm' CHECK (matched_by IN ('llm', 'keyword_fallback')),
    llm_raw    TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    UNIQUE(job_id, user_id)
);

-- ── RAG View: Consolidated Resume Snapshots ──────────────────────────

CREATE OR REPLACE VIEW rag_resume_snapshots AS
SELECT
    r.id AS resume_id,
    r.user_id,
    r.version_name,
    r.professional_summary,
    r.summary_embedding,
    CONCAT(
        'Summary: ', r.professional_summary, ' \n ',
        'Skills: ', COALESCE((SELECT string_agg(skill_name, ', ') FROM skills WHERE resume_id = r.id), ''), ' \n ',
        'Experience: ', COALESCE((SELECT string_agg(CONCAT(job_title, ' at ', company_name), '; ') FROM work_experience WHERE resume_id = r.id), '')
    ) AS full_metadata_text
FROM resumes r;
