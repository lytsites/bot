BEGIN;

CREATE TABLE IF NOT EXISTS local_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES local_users(id)
);

CREATE INDEX IF NOT EXISTS idx_local_sessions_user_id ON local_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_local_sessions_expires_at ON local_sessions(expires_at);

COMMIT;
