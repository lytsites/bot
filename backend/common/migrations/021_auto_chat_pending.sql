-- Add durable pending-processing fields for auto chat.
ALTER TABLE auto_chat_dialogs ADD COLUMN pending_incoming INTEGER DEFAULT 0;
ALTER TABLE auto_chat_dialogs ADD COLUMN last_ai_request_at TEXT;
ALTER TABLE auto_chat_dialogs ADD COLUMN last_ai_latency_ms INTEGER;

CREATE INDEX IF NOT EXISTS idx_auto_chat_dialogs_account_pending
ON auto_chat_dialogs(account_id, pending_incoming);

