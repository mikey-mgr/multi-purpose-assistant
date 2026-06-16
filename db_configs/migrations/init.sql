-- PostgreSQL initialisation for ai_assistant database
-- Run: psql -U postgres -f init.sql

CREATE DATABASE ai_assistant;

\c ai_assistant;

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
    scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scraped_jobs_site ON scraped_jobs(site);
CREATE INDEX IF NOT EXISTS idx_scraped_jobs_date_posted ON scraped_jobs(date_posted);
CREATE INDEX IF NOT EXISTS idx_scraped_jobs_scraped_at ON scraped_jobs(scraped_at);
