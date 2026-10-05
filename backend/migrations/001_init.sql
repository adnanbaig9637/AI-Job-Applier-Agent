-- ============================================================================
-- job_auto_pilot — Initial schema migration
-- ============================================================================
-- Database: job_auto_pilot (PostgreSQL 14+)
-- Run: psql -U postgres -d job_auto_pilot -f backend/migrations/001_init.sql
-- ============================================================================

-- ---------- Extensions ----------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid()

-- ---------- Enums ----------
DO $$ BEGIN
  CREATE TYPE run_status            AS ENUM ('pending','running','paused_hitl','completed','failed','stopped');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE log_level             AS ENUM ('info','warn','error','critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE application_status    AS ENUM ('applied','external','skipped','failed','rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE intervention_type     AS ENUM ('linkedin_login','captcha','mfa','manual_confirm','failed_question','other');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE intervention_status   AS ENUM ('pending','resolved','timeout');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE linkedin_session_status AS ENUM ('pending','logged_in','expired','failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE browser_provider       AS ENUM ('cdp_windows','cdp_linux_xvfb','novnc','none');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE user_role             AS ENUM ('user','admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================================
-- 1. users
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    phone           VARCHAR(20),
    password_hash   VARCHAR(255) NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    role            user_role    NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 2. user_profiles  (1:1 with users — maps config/personals.py + questions.py)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID         NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    -- personals.py
    first_name           VARCHAR(100) NOT NULL,
    middle_name          VARCHAR(100) NOT NULL DEFAULT '',
    last_name            VARCHAR(100) NOT NULL,
    phone_number         VARCHAR(20)  NOT NULL,
    current_city         VARCHAR(100) NOT NULL DEFAULT '',
    street               VARCHAR(255) NOT NULL DEFAULT '',
    state                VARCHAR(100) NOT NULL DEFAULT '',
    zipcode              VARCHAR(20)  NOT NULL DEFAULT '',
    country              VARCHAR(100) NOT NULL DEFAULT '',
    ethnicity            VARCHAR(50)  NOT NULL DEFAULT 'Decline',
    gender               VARCHAR(50)  NOT NULL DEFAULT '',
    disability_status    VARCHAR(20)  NOT NULL DEFAULT 'No',
    veteran_status       VARCHAR(20)  NOT NULL DEFAULT 'Decline',
    -- questions.py (profile-level)
    years_of_experience  VARCHAR(10)  NOT NULL DEFAULT '0',
    require_visa         VARCHAR(5)   NOT NULL DEFAULT 'No',
    website              TEXT         NOT NULL DEFAULT '',
    linkedin_url         TEXT         NOT NULL DEFAULT '',
    us_citizenship       VARCHAR(100) NOT NULL DEFAULT '',
    desired_salary       INTEGER      NOT NULL DEFAULT 0,
    current_ctc         INTEGER      NOT NULL DEFAULT 0,
    currency             VARCHAR(10)  NOT NULL DEFAULT 'INR',
    notice_period        INTEGER      NOT NULL DEFAULT 30,
    linkedin_headline    TEXT         NOT NULL DEFAULT '',
    linkedin_summary     TEXT         NOT NULL DEFAULT '',
    cover_letter         TEXT         NOT NULL DEFAULT '',
    user_information_all TEXT         NOT NULL DEFAULT '',
    recent_employer      VARCHAR(255) NOT NULL DEFAULT '',
    confidence_level     VARCHAR(5)   NOT NULL DEFAULT '5',
    pause_before_submit       BOOLEAN  NOT NULL DEFAULT FALSE,
    pause_at_failed_question BOOLEAN  NOT NULL DEFAULT TRUE,
    overwrite_previous_answers BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 3. job_preferences  (1:1 with users — maps config/search.py)
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_preferences (
    id                       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID         NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    search_terms             TEXT[]       NOT NULL DEFAULT '{}',
    search_location          VARCHAR(255) NOT NULL DEFAULT '',
    switch_number            INTEGER      NOT NULL DEFAULT 30,
    randomize_search_order   BOOLEAN      NOT NULL DEFAULT FALSE,
    sort_by                  VARCHAR(50)  NOT NULL DEFAULT 'Most recent',
    date_posted              VARCHAR(50)  NOT NULL DEFAULT 'Past week',
    salary                   VARCHAR(50)  NOT NULL DEFAULT '',
    easy_apply_only          BOOLEAN      NOT NULL DEFAULT TRUE,
    experience_level         TEXT[]       NOT NULL DEFAULT '{}',
    job_type                 TEXT[]       NOT NULL DEFAULT '{}',
    on_site                  TEXT[]       NOT NULL DEFAULT '{}',
    companies                TEXT[]       NOT NULL DEFAULT '{}',
    location                 TEXT[]       NOT NULL DEFAULT '{}',
    industry                 TEXT[]       NOT NULL DEFAULT '{}',
    job_function             TEXT[]       NOT NULL DEFAULT '{}',
    job_titles               TEXT[]       NOT NULL DEFAULT '{}',
    benefits                 TEXT[]       NOT NULL DEFAULT '{}',
    commitments              TEXT[]       NOT NULL DEFAULT '{}',
    under_10_applicants      BOOLEAN      NOT NULL DEFAULT FALSE,
    in_your_network          BOOLEAN      NOT NULL DEFAULT FALSE,
    fair_chance_employer    BOOLEAN      NOT NULL DEFAULT FALSE,
    pause_after_filters      BOOLEAN      NOT NULL DEFAULT FALSE,
    about_company_bad_words  TEXT[]       NOT NULL DEFAULT '{}',
    about_company_good_words TEXT[]       NOT NULL DEFAULT '{}',
    bad_words                TEXT[]       NOT NULL DEFAULT '{}',
    security_clearance       BOOLEAN      NOT NULL DEFAULT FALSE,
    did_masters              BOOLEAN      NOT NULL DEFAULT FALSE,
    current_experience       INTEGER      NOT NULL DEFAULT -1,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 4. resumes  (metadata only; files on disk under uploads/{user_id}/)
-- ============================================================================
CREATE TABLE IF NOT EXISTS resumes (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename     VARCHAR(255) NOT NULL,
    stored_path  TEXT         NOT NULL,
    size_bytes   BIGINT       NOT NULL DEFAULT 0,
    mime_type    VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    is_default   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id);

-- ============================================================================
-- 5. agent_configs  (maps config/settings.py + secrets.py AI settings)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_configs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name             VARCHAR(100) NOT NULL DEFAULT 'default',
    settings_json    JSONB        NOT NULL DEFAULT '{}',
    ai_settings_json JSONB        NOT NULL DEFAULT '{}',
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_configs_user ON agent_configs(user_id);

-- ============================================================================
-- 6. linkedin_sessions  (encrypted credentials + cookies)
-- ============================================================================
CREATE TABLE IF NOT EXISTS linkedin_sessions (
    id            UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID                    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username      VARCHAR(255)            NOT NULL,
    password_enc  BYTEA                   NOT NULL,        -- AES-GCM ciphertext
    cookies_enc   BYTEA,                                   -- AES-GCM encrypted JSON
    profile_dir   TEXT,
    status        linkedin_session_status NOT NULL DEFAULT 'pending',
    last_used_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ             NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ             NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_linkedin_sessions_user ON linkedin_sessions(user_id);

-- ============================================================================
-- 7. agent_runs
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_config_id       UUID        REFERENCES agent_configs(id) ON DELETE SET NULL,
    status                run_status  NOT NULL DEFAULT 'pending',
    pid                   INTEGER,
    started_at            TIMESTAMPTZ,
    ended_at              TIMESTAMPTZ,
    easy_applied_count    INTEGER     NOT NULL DEFAULT 0,
    external_jobs_count   INTEGER     NOT NULL DEFAULT 0,
    failed_count          INTEGER     NOT NULL DEFAULT 0,
    skip_count            INTEGER     NOT NULL DEFAULT 0,
    total_runs            INTEGER     NOT NULL DEFAULT 0,
    error_message         TEXT,
    temp_config_dir       TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user        ON agent_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status      ON agent_runs(status);
-- Enforce one active run per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_one_active
    ON agent_runs(user_id)
    WHERE status IN ('running','paused_hitl');

-- ============================================================================
-- 8. agent_run_logs
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_run_logs (
    id          BIGSERIAL    PRIMARY KEY,
    run_id      UUID         NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    seq         INTEGER      NOT NULL,
    level       log_level    NOT NULL DEFAULT 'info',
    message     TEXT         NOT NULL,
    raw_line     TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_run_logs_run_seq ON agent_run_logs(run_id, seq);

-- ============================================================================
-- 9. job_applications
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_applications (
    id                  UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID               REFERENCES agent_runs(id) ON DELETE SET NULL,
    user_id             UUID               NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id              VARCHAR(100)       NOT NULL,
    title               TEXT,
    company             TEXT,
    work_location       TEXT,
    work_style          TEXT,
    about_job           TEXT,
    experience_required TEXT,
    skills_required     TEXT[]             NOT NULL DEFAULT '{}',
    hr_name             TEXT,
    hr_link            TEXT,
    resume_filename     TEXT,
    reposted            BOOLEAN            NOT NULL DEFAULT FALSE,
    date_posted         TEXT,
    date_applied        TEXT,
    job_link            TEXT,
    external_job_link   TEXT,
    questions_found     JSONB,
    connect_request     TEXT,
    status              application_status NOT NULL DEFAULT 'applied',
    failure_reason      TEXT,
    screenshot_name      TEXT,
    created_at           TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ       NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_job_applications_user_status ON job_applications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_job_applications_user_date   ON job_applications(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_applications_job_id      ON job_applications(job_id);

-- ============================================================================
-- 10. human_intervention_requests
-- ============================================================================
CREATE TABLE IF NOT EXISTS human_intervention_requests (
    id           UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID                 NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    user_id      UUID                 NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type         intervention_type    NOT NULL DEFAULT 'other',
    prompt_text  TEXT                 NOT NULL,
    options      TEXT[]               NOT NULL DEFAULT '{}',
    resolution   TEXT,
    status       intervention_status  NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ          NOT NULL DEFAULT now(),
    resolved_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hitl_run_status ON human_intervention_requests(run_id, status);
CREATE INDEX IF NOT EXISTS idx_hitl_user_status ON human_intervention_requests(user_id, status);

-- ============================================================================
-- 11. browser_sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS browser_sessions (
    id                   UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id               UUID              NOT NULL UNIQUE REFERENCES agent_runs(id) ON DELETE CASCADE,
    provider             browser_provider  NOT NULL DEFAULT 'none',
    cdp_url              TEXT,
    debugging_port       INTEGER,
    last_screenshot_path TEXT,
    created_at           TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ       NOT NULL DEFAULT now()
);

-- ---------- updated_at trigger helper ----------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'users','user_profiles','job_preferences','resumes','agent_configs',
        'linkedin_sessions','agent_runs','job_applications','browser_sessions'
    ])
    LOOP
        EXECUTE format($f$
            CREATE TRIGGER trg_%s_updated
            BEFORE UPDATE ON %I
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        $f$, t, t);
    END LOOP;
END $$;

-- ---------- Done ----------
-- \echo 'Schema 001_init.sql applied successfully.'
