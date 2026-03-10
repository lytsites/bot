CREATE TABLE IF NOT EXISTS service_restart_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_key TEXT NOT NULL,
    system_unit TEXT NOT NULL,
    requested_by_user_id INTEGER NOT NULL,
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL,
    processed_at TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_service_restart_requests_service_requested_at
    ON service_restart_requests(service_key, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_service_restart_requests_status_requested_at
    ON service_restart_requests(status, requested_at ASC);
