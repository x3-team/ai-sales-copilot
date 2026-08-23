-- LPR webhook jobs (persist across Render restarts when DATABASE_URL is set)

CREATE TABLE IF NOT EXISTS lpr_jobs (
    job_id VARCHAR(36) PRIMARY KEY,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL,
    inn VARCHAR(12),
    company_name TEXT,
    platforms JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    webhook_url TEXT,
    result_url TEXT,
    candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provider_response JSONB
);

CREATE INDEX IF NOT EXISTS idx_lpr_jobs_created_at ON lpr_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_lpr_jobs_inn ON lpr_jobs(inn);
