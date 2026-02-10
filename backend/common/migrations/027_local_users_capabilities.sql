BEGIN;

-- Feature flags / service access control for local users.
-- Defaults keep existing installations working as before.

ALTER TABLE local_users ADD COLUMN service_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE local_users ADD COLUMN feature_group_reading_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE local_users ADD COLUMN feature_auto_dialogs_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE local_users ADD COLUMN disabled_comment TEXT;

COMMIT;

