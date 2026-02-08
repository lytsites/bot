BEGIN;

ALTER TABLE auth_flows ADD COLUMN method TEXT NOT NULL DEFAULT 'code';
ALTER TABLE auth_flows ADD COLUMN qr_token TEXT;
ALTER TABLE auth_flows ADD COLUMN qr_expires_at TEXT;
ALTER TABLE auth_flows ADD COLUMN qr_refresh_after TEXT;
ALTER TABLE auth_flows ADD COLUMN error_message TEXT;

COMMIT;
