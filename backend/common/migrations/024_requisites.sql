BEGIN;

CREATE TABLE IF NOT EXISTS requisites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    chat_id INTEGER,
    dialog_id INTEGER,
    message_id INTEGER,
    message_text TEXT,
    sender_phone TEXT,
    sender_username TEXT,
    requisite_type TEXT NOT NULL,
    country TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (chat_id) REFERENCES group_listeners(chat_id) ON DELETE SET NULL,
    FOREIGN KEY (dialog_id) REFERENCES auto_chat_dialogs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_requisites_account_id ON requisites(account_id);
CREATE INDEX IF NOT EXISTS idx_requisites_chat_id ON requisites(chat_id);
CREATE INDEX IF NOT EXISTS idx_requisites_dialog_id ON requisites(dialog_id);
CREATE INDEX IF NOT EXISTS idx_requisites_requisite_type ON requisites(requisite_type);
CREATE INDEX IF NOT EXISTS idx_requisites_country ON requisites(country);
CREATE INDEX IF NOT EXISTS idx_requisites_created_at ON requisites(created_at);

COMMIT;