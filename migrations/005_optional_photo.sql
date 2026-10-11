-- Additive metadata only: historical photo arrays and family data are untouched.
ALTER TABLE reports ADD COLUMN IF NOT EXISTS photo_upload_failed boolean NOT NULL DEFAULT false;
-- Keep sequence-generated identifiers growing beyond eight digits without truncation.
CREATE OR REPLACE FUNCTION report_number_label(number bigint) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT 'RPA-' || lpad(number::text,greatest(8,length(number::text)),'0')
$$;
ALTER TABLE reports ALTER COLUMN id SET DEFAULT report_number_label(nextval('report_number'));
