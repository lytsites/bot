BEGIN;

CREATE TABLE IF NOT EXISTS alert_bot_incident_sent (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);

COMMIT;
