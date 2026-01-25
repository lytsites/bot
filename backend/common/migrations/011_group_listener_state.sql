BEGIN;

ALTER TABLE group_listeners ADD COLUMN last_message_id INTEGER;

COMMIT;
