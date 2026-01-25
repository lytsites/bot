BEGIN;

CREATE TABLE IF NOT EXISTS group_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    title TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_catalog_account_chat
ON group_catalog(account_id, chat_id);

COMMIT;
