-- Relationship Nurturing System
-- Run after init.sql: psql -d ai_assistant -f add_relationship_tables.sql
--
-- Provides the full schema for #9 (Contact Architecture) and the
-- foundation for #7 (Referral Bridge) and #10 (Reminder Engine).

-- ── Contacts (your network) ──────────────────────────────────────────
-- Separate from `users` (which is YOU, the job seeker).
-- `current_company` is the key field for #7 referral matching.

CREATE TABLE IF NOT EXISTS contacts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name       VARCHAR(100) NOT NULL,
    last_name        VARCHAR(100) NOT NULL,
    email            VARCHAR(255),
    phone            VARCHAR(20),
    current_company  VARCHAR(150),       -- matches scraped_jobs.company for referral matching
    job_title        VARCHAR(150),
    linkedin_url     VARCHAR(255),
    location_city    VARCHAR(100),
    location_country VARCHAR(100),
    source           VARCHAR(50) DEFAULT 'manual',  -- 'manual', 'linkedin_export', 'google_contacts', 'whatsapp'
    source_id        VARCHAR(255),                  -- external ID from the source
    notes            TEXT,
    last_imported_at TIMESTAMP WITH TIME ZONE,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_contacts_email          ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_current_company ON contacts(current_company);

-- ── Contact Strategic Profiles (#9 Layer 2/3) ───────────────────────

CREATE TABLE IF NOT EXISTS contact_profiles (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id           UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    professional_summary TEXT,
    business_interests   TEXT[],
    hobbies              TEXT[],
    birthday             DATE,
    anniversary          DATE,
    relationship_strength INTEGER DEFAULT 50 CHECK (relationship_strength >= 0 AND relationship_strength <= 100),
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    UNIQUE(contact_id)
);

-- ── Contact Family (#9 Layer 3) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS contact_family (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    family_member_name VARCHAR(100) NOT NULL,
    relation_type     VARCHAR(50) NOT NULL,   -- 'spouse', 'child', 'parent', 'sibling'
    birthday          DATE,
    notes             TEXT
);

-- ── Contact Education (#9 Layer 3) ──────────────────────────────────

CREATE TABLE IF NOT EXISTS contact_education (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    institution     VARCHAR(150) NOT NULL,
    degree_type     VARCHAR(50),
    field_of_study  VARCHAR(100),
    graduation_year INTEGER
);

-- ── Contact Groups / Categories (#9 Layer 6) ────────────────────────

CREATE TABLE IF NOT EXISTS contact_groups (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_name  VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS contact_group_memberships (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id  UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    group_id    UUID NOT NULL REFERENCES contact_groups(id) ON DELETE CASCADE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    UNIQUE(contact_id, group_id)
);

-- ── Interaction History (#9 Layer 5) ────────────────────────────────

CREATE TABLE IF NOT EXISTS contact_interactions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    interaction_type  VARCHAR(50) NOT NULL,  -- 'call', 'message', 'email', 'meeting', 'birthday_acknowledgment'
    direction         VARCHAR(10) NOT NULL,  -- 'incoming', 'outgoing'
    notes             TEXT,
    context           TEXT,                  -- what was discussed
    value_provided    TEXT,                  -- what value did you give?
    follow_up_date    DATE,
    followed_up_at    TIMESTAMP WITH TIME ZONE,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_contact_interactions_contact   ON contact_interactions(contact_id);
CREATE INDEX IF NOT EXISTS idx_contact_interactions_created   ON contact_interactions(created_at);

-- ── AI Outreach Suggestions (#9 Layer 3) ────────────────────────────

CREATE TABLE IF NOT EXISTS contact_outreach_suggestions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    suggestion_type   VARCHAR(50) NOT NULL,  -- 'conversation_starter', 'value_offer', 'milestone_message'
    content           TEXT NOT NULL,
    generated_at      TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    used_at           TIMESTAMP WITH TIME ZONE,
    rating            INTEGER CHECK (rating >= 1 AND rating <= 5)
);

-- ── Milestone Tracking (#9 Layer 4) ─────────────────────────────────

CREATE TABLE IF NOT EXISTS contact_milestones (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    milestone_type    VARCHAR(50) NOT NULL,  -- 'birthday', 'work_anniversary', 'custom'
    milestone_date    DATE NOT NULL,
    description       TEXT,
    acknowledged_at   TIMESTAMP WITH TIME ZONE,
    message_sent_at   TIMESTAMP WITH TIME ZONE,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_contact_milestones_date ON contact_milestones(milestone_date);

-- ── Referral Tracking (extension of job_matches) ────────────────────
-- Links a matched job to a contact who can refer you.
-- Powered by #7: cross-reference matches against your network.

CREATE TABLE IF NOT EXISTS job_referral_opportunities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_match_id        UUID NOT NULL REFERENCES job_matches(id) ON DELETE CASCADE,
    contact_id          UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    status              VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'reached_out', 'responded_yes', 'responded_no', 'referral_sent'
    reached_out_at      TIMESTAMP WITH TIME ZONE,
    response            TEXT,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT timezone('Africa/Harare', CURRENT_TIMESTAMP),
    UNIQUE(job_match_id, contact_id)
);

-- ── Views ────────────────────────────────────────────────────────────

-- #7: Find jobs where you know someone at the company
CREATE OR REPLACE VIEW referral_opportunities AS
SELECT
    jm.id AS job_match_id,
    jm.job_id,
    jm.user_id,
    jm.status AS match_status,
    jm.score,
    sj.title AS job_title,
    sj.company,
    sj.location AS job_location,
    sj.job_url,
    c.id AS contact_id,
    c.first_name AS contact_first_name,
    c.last_name AS contact_last_name,
    c.job_title AS contact_job_title,
    c.email AS contact_email,
    c.phone AS contact_phone,
    c.linkedin_url AS contact_linkedin,
    cp.relationship_strength,
    jro.status AS referral_status
FROM job_matches jm
JOIN scraped_jobs sj ON sj.id = jm.job_id
JOIN contacts c ON LOWER(TRIM(c.current_company)) = LOWER(TRIM(sj.company))
LEFT JOIN contact_profiles cp ON cp.contact_id = c.id
LEFT JOIN job_referral_opportunities jro ON jro.job_match_id = jm.id AND jro.contact_id = c.id
WHERE jm.status IN ('matched', 'generated', 'applied');

-- Stale contacts: no interaction in 60+ days
CREATE OR REPLACE VIEW stale_contacts AS
SELECT
    c.id,
    c.first_name,
    c.last_name,
    c.email,
    c.phone,
    c.current_company,
    c.job_title,
    MAX(ci.created_at) AS last_contact,
    CASE
        WHEN MAX(ci.created_at) IS NULL THEN (CURRENT_DATE - c.created_at::date)
        ELSE (CURRENT_DATE - MAX(ci.created_at)::date)
    END AS days_since_contact
FROM contacts c
LEFT JOIN contact_interactions ci ON ci.contact_id = c.id
GROUP BY c.id
HAVING
    MAX(ci.created_at) IS NULL
    OR (CURRENT_DATE - MAX(ci.created_at)::date) > 60;

-- Upcoming milestones (next 14 days)
CREATE OR REPLACE VIEW upcoming_milestones AS
SELECT
    cm.id AS milestone_id,
    cm.contact_id,
    c.first_name,
    c.last_name,
    cm.milestone_type,
    cm.milestone_date,
    cm.description,
    (cm.milestone_date - CURRENT_DATE) AS days_until
FROM contact_milestones cm
JOIN contacts c ON c.id = cm.contact_id
WHERE cm.milestone_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
  AND cm.acknowledged_at IS NULL
ORDER BY cm.milestone_date;
