ALTER TABLE companies ADD COLUMN IF NOT EXISTS card_status TEXT NOT NULL DEFAULT 'signal';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS triggers TEXT NOT NULL DEFAULT '[]';

CREATE INDEX IF NOT EXISTS idx_companies_card_status ON companies(card_status);
