BEGIN;

CREATE TEMP TABLE _tmp_default_local_users (
    id INTEGER PRIMARY KEY
);

INSERT OR IGNORE INTO _tmp_default_local_users(id)
SELECT id
FROM local_users
WHERE (login = 'admin1' AND password_hash = '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92')
   OR (login = 'admin2' AND password_hash = '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92')
   OR (login = 'lyttern.lu@gmail.com' AND password_hash = '1107c82fc14dcb88cbb262588d012d3958a13489aee45e2834cb64aec3b6d5ac');

CREATE TEMP TABLE _tmp_default_accounts (
    id INTEGER PRIMARY KEY
);

INSERT OR IGNORE INTO _tmp_default_accounts(id)
SELECT id
FROM accounts
WHERE local_user_id IN (SELECT id FROM _tmp_default_local_users);

DELETE FROM tg_sessions
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM auth_flows
WHERE account_id IN (SELECT id FROM _tmp_default_accounts)
   OR local_user_id IN (SELECT id FROM _tmp_default_local_users);

DELETE FROM events
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM jobs
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM group_listeners
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM group_matches
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM group_catalog
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM group_worker_runs
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM auto_chat_messages
WHERE dialog_id IN (
    SELECT id
    FROM auto_chat_dialogs
    WHERE account_id IN (SELECT id FROM _tmp_default_accounts)
);

DELETE FROM auto_chat_dialogs
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM requisites
WHERE account_id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM accounts
WHERE id IN (SELECT id FROM _tmp_default_accounts);

DELETE FROM local_sessions
WHERE user_id IN (SELECT id FROM _tmp_default_local_users);

DELETE FROM local_user_auto_chat_usernames
WHERE user_id IN (SELECT id FROM _tmp_default_local_users);

DELETE FROM local_user_auto_chat_settings
WHERE user_id IN (SELECT id FROM _tmp_default_local_users);

DELETE FROM local_user_settings
WHERE user_id IN (SELECT id FROM _tmp_default_local_users);

DELETE FROM local_users
WHERE id IN (SELECT id FROM _tmp_default_local_users);

DROP TABLE _tmp_default_accounts;
DROP TABLE _tmp_default_local_users;

COMMIT;
