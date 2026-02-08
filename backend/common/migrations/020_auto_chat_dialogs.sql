CREATE TABLE IF NOT EXISTS auto_chat_dialogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    peer_tg_user_id INTEGER NOT NULL,
    peer_username TEXT,
    peer_display_name TEXT,
    status TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    stopped_at TEXT,
    last_incoming_tg_message_id INTEGER,
    last_outgoing_tg_message_id INTEGER,
    UNIQUE(account_id, peer_tg_user_id),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auto_chat_dialogs_account_status
ON auto_chat_dialogs(account_id, status);

CREATE TABLE IF NOT EXISTS auto_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dialog_id INTEGER NOT NULL,
    direction TEXT NOT NULL, -- IN / OUT / SYS
    text TEXT NOT NULL,
    tg_message_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(dialog_id) REFERENCES auto_chat_dialogs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auto_chat_messages_dialog_id
ON auto_chat_messages(dialog_id, id);
