ALTER TABLE reports ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS archived_by text;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS dedup_keys text[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS reports_request_hash ON reports(request_hash);
CREATE INDEX IF NOT EXISTS reports_dedup_keys ON reports USING gin(dedup_keys);
CREATE INDEX IF NOT EXISTS reports_phone ON reports((data->>'phone'));
-- Only opaque filenames: durable retry for unlink after transactional erasure.
CREATE TABLE IF NOT EXISTS photo_cleanup (filename text PRIMARY KEY CHECK(filename ~ '^[a-f0-9]{32}\.jpg$'));
-- Minimal erasure ledger; no name, phone, location, photos or report content.
CREATE TABLE IF NOT EXISTS deleted_reports (id text PRIMARY KEY, deleted_at timestamptz NOT NULL DEFAULT now());
