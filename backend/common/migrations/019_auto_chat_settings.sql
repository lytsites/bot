CREATE TABLE IF NOT EXISTS local_user_auto_chat_settings (
    user_id INTEGER PRIMARY KEY,
    ai_instruction TEXT NOT NULL DEFAULT '',
    greeting_examples TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES local_users(id) ON DELETE CASCADE
);
