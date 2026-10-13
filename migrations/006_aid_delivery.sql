-- Módulo de entrega de ayudas, separado de los reportes ciudadanos.
-- Migración idempotente; no altera las tablas de reportes existentes.
CREATE TABLE IF NOT EXISTS aid_workers (
 id uuid PRIMARY KEY,
 full_name text NOT NULL CHECK (length(trim(full_name)) BETWEEN 3 AND 180),
 login_name text NOT NULL UNIQUE,
 secret_hash text NOT NULL,
 active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(),
 revoked_at timestamptz
);
CREATE TABLE IF NOT EXISTS aid_worker_sessions (
 token_hash text PRIMARY KEY,
 worker_id uuid NOT NULL REFERENCES aid_workers(id),
 expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS aid_worker_sessions_expiry ON aid_worker_sessions(expires_at);
CREATE TABLE IF NOT EXISTS aid_deliveries (
 id uuid PRIMARY KEY,
 worker_id uuid NOT NULL REFERENCES aid_workers(id),
 beneficiary_name text NOT NULL CHECK(length(trim(beneficiary_name)) BETWEEN 3 AND 180),
 beneficiary_id text NOT NULL CHECK(length(trim(beneficiary_id)) BETWEEN 3 AND 50),
 place text NOT NULL CHECK(length(trim(place)) BETWEEN 3 AND 300),
 aid_type text NOT NULL CHECK(length(trim(aid_type)) BETWEEN 3 AND 500),
 idempotency_key uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(worker_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS aid_deliveries_created ON aid_deliveries(created_at DESC);
CREATE INDEX IF NOT EXISTS aid_deliveries_worker ON aid_deliveries(worker_id,created_at DESC);
