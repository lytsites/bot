BEGIN;

CREATE TABLE IF NOT EXISTS incident_resolution (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    is_resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT,
    resolved_by_user_id INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_incident_resolution_resolved
ON incident_resolution(is_resolved);

COMMIT;
