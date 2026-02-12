BEGIN;

-- Intentionally no-op.
-- Previous versions of this migration removed default local users and all related data.
-- This behavior is disabled to avoid unintended data loss on deploy.

COMMIT;
