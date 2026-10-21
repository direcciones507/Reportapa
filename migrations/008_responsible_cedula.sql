-- Optional private field in the existing reports.data JSONB document.
-- No UPDATE, backfill, uniqueness rule or change to household deduplication.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='reports'::regclass AND conname='reports_cedula_format') THEN
  ALTER TABLE reports ADD CONSTRAINT reports_cedula_format CHECK (
   NOT (data ? 'cedula') OR data->'cedula' = 'null'::jsonb OR
   (jsonb_typeof(data->'cedula') = 'string' AND data->>'cedula' ~ '^[A-Z0-9]{1,6}-[0-9]{1,6}-[0-9]{1,6}$')
  ) NOT VALID;
 END IF;
END $$;
ALTER TABLE reports VALIDATE CONSTRAINT reports_cedula_format;
