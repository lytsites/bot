BEGIN;

CREATE TABLE IF NOT EXISTS group_worker_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    last_error TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_group_worker_runs_account
ON group_worker_runs(account_id);

CREATE INDEX IF NOT EXISTS idx_group_worker_runs_status
ON group_worker_runs(status);

COMMIT;
