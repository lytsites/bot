-- Per-local-user auto chat simulation settings.
ALTER TABLE local_user_auto_chat_settings ADD COLUMN delay_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE local_user_auto_chat_settings ADD COLUMN delay_min_ms INTEGER NOT NULL DEFAULT 0;
ALTER TABLE local_user_auto_chat_settings ADD COLUMN delay_max_ms INTEGER NOT NULL DEFAULT 0;
ALTER TABLE local_user_auto_chat_settings ADD COLUMN typing_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE local_user_auto_chat_settings ADD COLUMN read_enabled INTEGER NOT NULL DEFAULT 0;

