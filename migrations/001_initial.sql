CREATE SEQUENCE IF NOT EXISTS report_number;
CREATE TABLE IF NOT EXISTS reports (
 id text PRIMARY KEY DEFAULT ('RPA-' || lpad(nextval('report_number')::text, 8, '0')),
 created_at timestamptz NOT NULL DEFAULT now(),
 idempotency_key uuid UNIQUE NOT NULL,
 request_hash text NOT NULL,
 fingerprint text NOT NULL,
 data jsonb NOT NULL,
 status text NOT NULL DEFAULT 'pendiente' CHECK(status IN ('pendiente','contactado','visitado')),
 photos jsonb NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS reports_fingerprint ON reports(fingerprint);
CREATE INDEX IF NOT EXISTS reports_data ON reports USING gin(data);
CREATE TABLE IF NOT EXISTS request_limits (key text PRIMARY KEY, started_at timestamptz NOT NULL DEFAULT now(), count integer NOT NULL);
