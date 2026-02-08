CREATE TABLE IF NOT EXISTS local_user_auto_chat_usernames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, username),
    FOREIGN KEY(user_id) REFERENCES local_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auto_chat_usernames_user
ON local_user_auto_chat_usernames(user_id);
