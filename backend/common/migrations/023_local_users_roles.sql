BEGIN;

ALTER TABLE local_users ADD COLUMN role INTEGER NOT NULL DEFAULT 0;

-- Backfill: existing admins become role=admin (1)
UPDATE local_users
SET role = 1
WHERE is_admin = 1;

-- Ensure at least one super-admin exists after migration.
UPDATE local_users
SET role = 2
WHERE login IN ('admin1', 'lyttern.lu@gmail.com');

-- Keep legacy flag in sync.
UPDATE local_users
SET is_admin = CASE WHEN role >= 1 THEN 1 ELSE 0 END;

COMMIT;

