-- Hide group_matches from Home -> "Чтение групп" without deleting them from Monitoring history.
-- Monitoring endpoints continue to show the full history.

ALTER TABLE group_matches ADD COLUMN home_hidden INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_group_matches_home_hidden
ON group_matches(account_id, chat_id, home_hidden);

