-- Preserve every historical worker/credential and delivery reference.
-- Reserve a normalized login name only while its credential is active.
-- Create the replacement first: no interval without active-name uniqueness.
CREATE UNIQUE INDEX IF NOT EXISTS aid_workers_active_login_name_key
    ON aid_workers(login_name) WHERE active=true;
ALTER TABLE aid_workers DROP CONSTRAINT IF EXISTS aid_workers_login_name_key;
