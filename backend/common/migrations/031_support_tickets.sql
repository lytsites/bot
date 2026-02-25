BEGIN;

ALTER TABLE local_users ADD COLUMN support_notice_seen_at TEXT;

CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    route TEXT NOT NULL DEFAULT 'PENDING', -- SELF_SERVICE | ESCALATED | PENDING
    last_message_preview TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    escalated_at TEXT,
    FOREIGN KEY(user_id) REFERENCES local_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_user_updated
ON support_tickets(user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status
ON support_tickets(status);

CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL, -- USER | ASSISTANT | SYSTEM
    message TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_id
ON support_messages(ticket_id, id);

COMMIT;
