BEGIN;

ALTER TABLE auth_flows ADD COLUMN local_user_id INTEGER;

ALTER TABLE accounts ADD COLUMN local_user_id INTEGER;

UPDATE accounts
SET local_user_id = (SELECT id FROM local_users WHERE login='admin1')
WHERE local_user_id IS NULL
  AND EXISTS (SELECT 1 FROM local_users WHERE login='admin1');

COMMIT;
