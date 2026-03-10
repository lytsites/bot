CREATE TABLE IF NOT EXISTS system_flags (
    flag_key TEXT PRIMARY KEY,
    value_text TEXT NOT NULL DEFAULT '',
    expires_at TEXT,
    updated_at TEXT NOT NULL
);
