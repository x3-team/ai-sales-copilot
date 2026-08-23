-- SQLite fallback schema (local dev / tests without DATABASE_URL)

CREATE TABLE IF NOT EXISTS companies (
    inn TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    website TEXT,
    sources TEXT NOT NULL DEFAULT '[]',
    enrich_payload TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fio TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    company_inn TEXT NOT NULL REFERENCES companies(inn) ON DELETE CASCADE,
    stakeholder TEXT NOT NULL CHECK (stakeholder IN ('ceo', 'lpr', 'lvr', 'ldpr')),
    profile_url TEXT,
    platform TEXT,
    sources TEXT NOT NULL DEFAULT '[]',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (company_inn, stakeholder)
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('email', 'phone', 'telegram')),
    value TEXT NOT NULL,
    source_url TEXT,
    found_at REAL NOT NULL,
    UNIQUE (person_id, type, value)
);

CREATE TABLE IF NOT EXISTS power_maps (
    inn TEXT PRIMARY KEY REFERENCES companies(inn) ON DELETE CASCADE,
    ceo_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    lpr_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    lvr_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    ldpr_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_people_company_inn ON people(company_inn);
CREATE INDEX IF NOT EXISTS idx_contacts_person_id ON contacts(person_id);
