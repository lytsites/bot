BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_matches_unique
ON group_matches(account_id, chat_id, message_id);

COMMIT;
