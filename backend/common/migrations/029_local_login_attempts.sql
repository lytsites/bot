BEGIN;

CREATE TABLE IF NOT EXISTS local_login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    login TEXT NOT NULL,
    ip TEXT,
    user_agent TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES local_users(id)
);

CREATE INDEX IF NOT EXISTS idx_local_login_attempts_created_at
    ON local_login_attempts(created_at);

CREATE INDEX IF NOT EXISTS idx_local_login_attempts_login_created_at
    ON local_login_attempts(login, created_at);

CREATE INDEX IF NOT EXISTS idx_local_login_attempts_ip_created_at
    ON local_login_attempts(ip, created_at);

CREATE INDEX IF NOT EXISTS idx_local_login_attempts_user_id_created_at
    ON local_login_attempts(user_id, created_at);

COMMIT;
