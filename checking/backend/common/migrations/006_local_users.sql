BEGIN;

CREATE TABLE IF NOT EXISTS local_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    keywords TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES local_users(id)
);

ALTER TABLE accounts ADD COLUMN local_user_id INTEGER;

INSERT OR IGNORE INTO local_users(login, password_hash, is_active, created_at, updated_at)
VALUES
  ('admin1', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 1, datetime('now'), datetime('now')),
  ('admin2', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 1, datetime('now'), datetime('now'));

INSERT OR IGNORE INTO local_user_settings(user_id, keywords, is_active, created_at, updated_at)
SELECT id, '', 1, datetime('now'), datetime('now')
FROM local_users
WHERE login IN ('admin1','admin2');

COMMIT;
