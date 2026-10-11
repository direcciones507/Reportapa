# Corrección de capacidad — 11 octubre 2026

Base: rama desplegada feat/reportapa-mvp-20261010, commit 69e82b8.
Producción permanece intacta; no fusionar ni desplegar sin autorización.

## Cambios

- Se retira el límite Uvicorn de 50 conexiones/tareas. No se sustituye por un número mayor arbitrario.
- Se acota el trabajo costoso antes de leer cuerpos: 8 envíos activos, hasta 128 solicitudes admitidas entre activas y pendientes; espera máxima 15 s. Saturación devuelve 503 con Retry-After y conserva la clave de reintento del ciudadano. Navegación no consume ese semáforo. Una instancia y un proceso: no aumentar réplicas mientras las fotos dependan del volumen local.
- Pool PostgreSQL: 2 conexiones iniciales, máximo 8; espera 10 s, máximo 64 pendientes, statement_timeout 15 s, lock_timeout 10 s. DB_POOL_MAX/SUBMISSION_WORKERS son configurables; valores por defecto sujetos a evidencia del ensayo. No se modifica max_connections productivo.
- Fotos/SQL del envío se ejecutan en trabajadores, fuera del bucle asíncrono. Fotos privadas 0600, fsync antes del COMMIT; reserva de 32 MiB de espacio antes de escribir. No cambia resolución/calidad ni fotografías históricas.
- Contador ciudadano por teléfono normalizado y firmado (20/15 min), independiente de IP compartida; honeypot, validación, tamaño y duplicados conservados. No se confía en cabeceras de IP. Login mantiene su protección de 10 intentos/origen; el proxy de producción todavía requiere verificación física de aislamiento del login.
- Limpieza de contadores cada 30 s, fuera de cada envío; se reutiliza el índice request_hash existente para envíos idénticos. Locks de duplicados ordenados.
- Ante pérdida de confirmación del COMMIT, se consulta idempotency_key antes de borrar fotos. Si la base no responde, se conservan los archivos privados y se devuelve error recuperable; requieren reconciliación posterior. Nunca borrar fotos con resultado SQL incierto.

## Ensayo reproducible

scripts/load_capacity.py solo acepta PostgreSQL localhost/127.0.0.1, base reportapa_test. Arranca Uvicorn loopback, crea carpeta de fotos temporal y usa únicamente registros sintéticos. TRUNCATE está restringido a esa base descartable. No carga producción.

Cada escenario progresa por 10, 25, 50, 100, 250, 500 y 1000 usuarios; se detiene ante errores >1%, p95 >5 s o RSS web >=1 GB. Navegación: tres HTTP por usuario (HTML/config/JS); envío: una solicitud multipart simultánea por usuario, sin fotos o con tres fotos JPEG sintéticas 1600×1200. No equivale a mil personas reales en Railway ni a conexiones persistentes de usuarios que están leyendo. Las ráfagas no equivalen a tasas sostenidas por minuto.

Salida JSON y artefacto CI: latencias p50/p95/p99, RPS, errores, CPU/RSS del proceso web, conexiones/locks PostgreSQL, persistencia de todos los IDs confirmados, fotos procesadas y tamaños, tiempo de clean_photo. CPU cliente/DB comparte runner; no se certifica capacidad productiva con este ensayo.

## Inventario observado Railway

ReportaPA project 5f63fcb0-a184-475a-9624-488f9703467d, production 8890a9f3-01df-4e7f-9b35-4c1ba58f0f14.
Web: una réplica, volumen 1024 MB, estado SUCCESS cdadaefe-5369-469d-b65c-5ffb133ce60d. Postgres 18: volumen 50000 MB, SUCCESS e743acf5-23cd-4a75-936e-7213e361494c.
Métricas de última hora: disco web 0.017309696 GB; disco PostgreSQL 0.8638464 GB. CPU/MEMORY_LIMIT de web 24/24 GB son límites de plataforma, no capacidad sostenida demostrada. DISK_USAGE no sustituye df/du ni tamaño de tablas/fotos. No hay proxy TCP PostgreSQL público y no se crea uno.

## Pendientes de certificación productiva

Se requiere lectura dentro del contenedor existente: df -B1 /data, sumatoria/tamaño medio/máximo de fotos sin abrir contenido ni mostrar nombres, pg_database_size, pg_total_relation_size, SHOW max_connections, pg_stat_activity, pg_locks. No hay comando SSH/SQL en el conector usado; inventario y métricas sí están disponibles. No asumir que DISK_USAGE es exclusivamente fotografías.

Capacidad sin fotos depende del tamaño real de filas/índices; con fotos suele limitar primero el volumen privado de 1 GB. Proyecciones: floor(espacio útil reservado/(n_fotos × tamaño foto)), combinada con límite DB. Cero fotos: límite DB. Mostrar siempre origen sintético/real de los tamaños. Volumen configurado es máximo, no uso facturable ni garantía de capacidad.

No se contratan recursos ni se amplían volúmenes. Estimación monetaria requiere tarifa Railway vigente y uso incremental CPU/RAM/disco; informar antes de solicitar autorización. Cambios del PR no agregan infraestructura; consumo después del despliegue depende del tráfico.

Tarifas consultadas 11-oct-2026 en https://docs.railway.com/pricing: volumen $0.15/GB/mes, RAM $10/GB/mes, CPU $20/vCPU/mes, egreso $0.05/GB. Escenario fotos de 1 a 5 GB: hasta $0.60/mes por 4 GB adicionales realmente ocupados; de 1 a 10 GB: hasta $1.35/mes por 9 GB adicionales. No incluye incremento CPU/RAM/egreso ni garantiza importe final de factura; créditos Pro y consumo de otros proyectos influyen. No aplicado.
