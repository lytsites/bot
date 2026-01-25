BEGIN;

CREATE TABLE IF NOT EXISTS group_listeners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    title TEXT,
    is_listening INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_listeners_account_chat
ON group_listeners(account_id, chat_id);

COMMIT;
