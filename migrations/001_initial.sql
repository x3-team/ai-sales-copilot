-- Sales Copilot persistent memory (companies, people, contacts, power_maps)
-- Safe to run multiple times (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS companies (
    inn VARCHAR(12) PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    website TEXT,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    enrich_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS people (
    id SERIAL PRIMARY KEY,
    fio TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    company_inn VARCHAR(12) NOT NULL REFERENCES companies(inn) ON DELETE CASCADE,
    stakeholder VARCHAR(8) NOT NULL CHECK (stakeholder IN ('ceo', 'lpr', 'lvr', 'ldpr')),
    profile_url TEXT,
    platform VARCHAR(32),
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_inn, stakeholder)
);

CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    type VARCHAR(16) NOT NULL CHECK (type IN ('email', 'phone', 'telegram')),
    value TEXT NOT NULL,
    source_url TEXT,
    found_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (person_id, type, value)
);

CREATE TABLE IF NOT EXISTS power_maps (
    inn VARCHAR(12) PRIMARY KEY REFERENCES companies(inn) ON DELETE CASCADE,
    ceo_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    lpr_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    lvr_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    ldpr_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_people_company_inn ON people(company_inn);
CREATE INDEX IF NOT EXISTS idx_contacts_person_id ON contacts(person_id);
CREATE INDEX IF NOT EXISTS idx_companies_updated_at ON companies(updated_at);
