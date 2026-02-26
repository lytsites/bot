BEGIN;

ALTER TABLE auto_chat_dialogs ADD COLUMN pending_buffer_until_at TEXT;

CREATE INDEX IF NOT EXISTS idx_auto_chat_dialogs_pending_buffer
ON auto_chat_dialogs(account_id, pending_incoming, pending_buffer_until_at);

COMMIT;
