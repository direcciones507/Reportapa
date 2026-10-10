ALTER TABLE reports ADD COLUMN IF NOT EXISTS estado_ayuda text NOT NULL DEFAULT 'pendiente_confirmar';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS ayuda_actualizada_at timestamptz;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS ayuda_observacion text NOT NULL DEFAULT '';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS ayuda_admin text;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS ayuda_historial jsonb NOT NULL DEFAULT '[]';
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='reports_estado_ayuda_check' AND conrelid='reports'::regclass) THEN
  ALTER TABLE reports ADD CONSTRAINT reports_estado_ayuda_check CHECK (estado_ayuda IN ('pendiente_confirmar','sin_ayuda','parcial','completa'));
 END IF;
END $$;
CREATE INDEX IF NOT EXISTS reports_estado_ayuda ON reports(estado_ayuda);
