-- Store which keyword(s) triggered a match, so highlighting remains stable even after keywords change.

ALTER TABLE group_matches ADD COLUMN matched_keywords TEXT;

CREATE INDEX IF NOT EXISTS idx_group_matches_matched_keywords
ON group_matches(account_id, chat_id, matched_keywords);

