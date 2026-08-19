-- Company card status and demand triggers

ALTER TABLE companies ADD COLUMN IF NOT EXISTS card_status VARCHAR(16) NOT NULL DEFAULT 'signal';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS triggers JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_companies_card_status ON companies(card_status);
