ALTER TABLE local_user_auto_chat_usernames ADD COLUMN tg_user_id INTEGER;
ALTER TABLE local_user_auto_chat_usernames ADD COLUMN display_name TEXT;
ALTER TABLE local_user_auto_chat_usernames ADD COLUMN status TEXT;

UPDATE local_user_auto_chat_usernames
SET status = COALESCE(status, 'UNKNOWN');
