BEGIN;

ALTER TABLE local_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;

INSERT OR IGNORE INTO local_users(login, password_hash, is_active, is_admin, created_at, updated_at)
VALUES ('lyttern.lu@gmail.com', '1107c82fc14dcb88cbb262588d012d3958a13489aee45e2834cb64aec3b6d5ac', 1, 1, datetime('now'), datetime('now'));

INSERT OR IGNORE INTO local_user_settings(user_id, keywords, is_active, created_at, updated_at)
SELECT id, '', 1, datetime('now'), datetime('now')
FROM local_users
WHERE login = 'lyttern.lu@gmail.com';

COMMIT;
