-- Server-side revocation for the existing signed owner sessions.
CREATE TABLE IF NOT EXISTS admin_sessions (
 token_hash text PRIMARY KEY,
 username text NOT NULL CHECK (username='Ayudapanama'),
 expires_at timestamptz NOT NULL,
 credential_hash text NOT NULL
);
CREATE INDEX IF NOT EXISTS admin_sessions_expiry ON admin_sessions(expires_at);
