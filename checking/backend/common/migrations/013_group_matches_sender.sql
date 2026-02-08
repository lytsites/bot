BEGIN;

ALTER TABLE group_matches ADD COLUMN sender_phone TEXT;

COMMIT;
