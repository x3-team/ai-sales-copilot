CREATE TABLE IF NOT EXISTS lpr_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL,
    inn TEXT,
    company_name TEXT,
    platforms TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    webhook_url TEXT,
    result_url TEXT,
    candidates TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    provider_response TEXT
);

CREATE INDEX IF NOT EXISTS idx_lpr_jobs_created_at ON lpr_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_lpr_jobs_inn ON lpr_jobs(inn);
