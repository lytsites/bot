BEGIN;

CREATE TABLE IF NOT EXISTS tg_sessions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    session_string TEXT NOT NULL,
    dc_id INTEGER,
    user_id INTEGER,
    updated_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

INSERT INTO tg_sessions_new(account_id, session_string, dc_id, user_id, updated_at, revoked_at)
SELECT account_id, session_string, dc_id, user_id, updated_at, revoked_at
FROM tg_sessions;

DROP TABLE tg_sessions;
ALTER TABLE tg_sessions_new RENAME TO tg_sessions;

CREATE INDEX IF NOT EXISTS idx_tg_sessions_account_id ON tg_sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_tg_sessions_revoked ON tg_sessions(revoked_at);

COMMIT;
