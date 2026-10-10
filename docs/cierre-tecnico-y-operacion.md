# Cierre técnico y operación

Auditoría del 10-10-2026 sobre PR #1 y rama feat/reportapa-mvp-20261010. No se fusionó ni publicó. Recepción permanece cerrada por defecto y en configuración de despliegue propuesta. Solo datos descartables en pruebas.

## Pendientes clasificados y correcciones ejecutadas

| Categoría | Elemento | Resultado |
| --- | --- | --- |
| Corregible inmediatamente | JSON mal formado en PATCH/DELETE devolvía error interno | Mismo parser de login y cambios privados devuelve 422; prueba sin modificaciones al reporte |
| Corregible inmediatamente | Foto referenciada pero ausente daba error interno | Ruta privada devuelve 404; PDF conserva ficha con aviso de foto no disponible |
| Corregible inmediatamente | Archivo creado con permisos del proceso antes de chmod; fallo parcial podía quedar fuera de limpieza | Creación exclusiva 0600 desde primer byte; registra nombre antes de escritura y reutiliza cola existente si falla unlink tras rollback |
| Corregible inmediatamente | Pruebas podían vaciar una base configurada por error | Fixture rechaza base ajena o remota antes de cambiar datos; solo reportapa_test local descartable |
| Corregible inmediatamente | Migraciones concurrentes podían competir al iniciar | Bloqueo transaccional advisory en el PostgreSQL existente, sin tabla ni migración nueva |
| Corregible inmediatamente | Teléfono con letras o URL se aceptaba al quitar caracteres | Valida caracteres permitidos antes de normalizar; conserva formatos usuales +507 |
| Corregible inmediatamente | COOKIE_SECURE mal escrito desactivaba cookie segura fuera de Railway | Arranque rechaza valores distintos de true/false |
| Corregible inmediatamente | Contexto Docker incluía archivos locales no requeridos | .dockerignore permite solo aplicación, migraciones, dependencias y Dockerfile |
| Corregible inmediatamente | Dos runs CI por cada commit del PR | Workflow por PR y ejecución manual, con concurrencia y timeout; sin despliegue. Healthcheck de PostgreSQL usa usuario/base correctos |
| Dependiente de autorización de costo | Web, PostgreSQL y dos volúmenes exclusivos | Ninguno creado. Objetivo USD 10 adicionales no autoriza contratación |
| Dependiente de Railway | HTTPS, dominio provisional, fotos persistentes tras redeploy, comportamiento de proxy y límite por peer | Configuración preparada; pendientes en infraestructura autorizada |
| Dependiente de Railway/autorización | Backups nativos y recuperación real | Ensayo lógico real en CI; snapshots Railway no creados ni certificados |
| Prueba física | Android, iPhone, tablet | Checklist existente; requiere despliegue cerrado autorizado |

No se construyen otra autenticación, almacenamiento ni sistema de seguimiento. La cola y el registro mínimo de borrados siguen en la misma base. Un cierre abrupto o pérdida simultánea de SQL y disco todavía puede dejar un archivo privado huérfano: no afirmar atomicidad entre disco y PostgreSQL. No se eliminan automáticamente archivos no referenciados de antigüedad desconocida.

## Inventario Railway confirmado

Workspace personal **direcciones507's Projects**, ID **7c9545b8-fb4d-4391-85e4-ab2b4622f1c4**. Listado actual: siete proyectos, cada uno con un entorno production accesible. No se encontró ReportaPA ni se reutilizó ningún servicio.

| Proyecto | Servicios encontrados (solo lectura) |
| --- | --- |
| empleos-pa | empleos-web-main, empleos-api-feature, Postgres |
| leveia-production-dark | @leveia/web, @leveia/api, Postgres-qtbC |
| leveia-staging | @leveia/web, @leveia/api, Postgres |
| meticulous-elegance | @leveia/web, @leveia/api, Postgres; fuentes LeveIA verificadas en auditoría anterior |
| amused-enchantment | ad507-core-shadow, ad507-core, n8n, Postgres; fuente Direcciones507 verificada anteriormente |
| magnificent-abundance | Sin servicios |
| clever-patience | Sin servicios |

El conector disponible lista workspace, proyectos y servicios, pero no expone plan contratado, crédito restante, factura ni límites de gasto. CLI Railway no está instalada en este entorno; no hay acceso autenticado alternativo comprobado para lectura de facturación. **Plan y saldo no confirmados**. No inferir Pro/Hobby a partir del número de proyectos, de la memoria o de que existan otros volúmenes. La única intervención necesaria para este dato es acceso/lectura de Usage/Billing del workspace; no es necesario dar tokens por chat.

Recursos nuevos creados: cero. Costos de infraestructura nuevos comprometidos: USD 0. No existe URL provisional verificable de ReportaPA. CI usa recursos efímeros de GitHub Actions existentes; no se afirma costo cero de la cuenta GitHub ni saldo ilimitado.

## Estimación frente al objetivo de USD 10 adicionales

Tarifas oficiales consultadas: RAM USD 10/GB-mes, CPU USD 20/vCPU-mes, volumen usado USD 0.15/GB-mes, egreso USD 0.05/GB. Los backups incrementales siguen tarifa de volumen para datos exclusivos. Estimación aritmética, **no medición del servicio ni cotización garantizada**:

| Consumo combinado web + PostgreSQL | Hipótesis reducida | Hipótesis alta |
| --- | ---: | ---: |
| RAM promedio | 0.40 GB = USD 4.00 | 0.75 GB = USD 7.50 |
| CPU promedio | 0.03 vCPU = USD 0.60 | 0.05 vCPU = USD 1.00 |
| Volumen usado, DB + fotos | 3 GB = USD 0.45 | 5 GB = USD 0.75 |
| Datos exclusivos de backups | 3 GB = USD 0.45 | 5 GB = USD 0.75 |
| Egreso | 2 GB = USD 0.10 | 5 GB = USD 0.25 |
| Total de consumo ilustrativo | USD 5.60/mes | USD 10.25/mes |

No suma un plan adicional automáticamente: el crédito y mínimo de la suscripción del workspace se relacionan con el consumo conjunto de todos los proyectos. Sin plan/saldo no se puede conocer el incremento exacto de la factura. Nuevos picos, más fotos o mayor RAM pueden superar USD 10. El escenario reducido deja margen, pero no prueba que el objetivo sea viable. No reducir recursos a ciegas ni habilitar sleep para la base; medir primero en un ensayo autorizado. Free admite un volumen por proyecto y la arquitectura requiere dos.

**Monitoreo preparado, no aplicado:** antes de provisionar, capturar consumo base de proyectos existentes; luego seguir únicamente el nuevo proyecto ReportaPA por CPU/RAM/volumen/backups/egreso y proyección mensual. Avisar al propietario si la proyección llega a USD 8 adicionales; revisar/cerrar recepción y suspender cambios según autorización antes de superar el objetivo. Un límite duro de USD 10 a nivel workspace puede apagar los otros proyectos: está prohibido cambiarlo bajo este alcance. No presentar un límite global como un tope exclusivo de ReportaPA. El objetivo no es autorización para contratar, crecer volúmenes ni cambiar facturación.

## Operación: decisiones y acciones autorizadas por fases

### 1. Activación de infraestructura

El propietario autoriza explícitamente gasto y creación. Confirmar plan/retención/capacidad y región antes de provisionar. Crear un proyecto ReportaPA en el workspace identificado; PostgreSQL exclusivo y web exclusiva, volumen de DB propio y volumen web en /data. Una instancia, misma región, sin replicas ni red TCP pública de DB. No reutilizar proyectos vacíos: tampoco son ReportaPA autorizado. La conexión de una fuente puede desplegar inmediatamente; realizarla solo en fase de despliegue autorizado. Las operaciones repetibles deben ejecutarlas el agente con herramientas disponibles, no devolverse como tareas al propietario.

### 2. Configuración segura de secretos y referencias

El propietario interviene para elegir/proporcionar ADMIN_PASSWORD de 16+ caracteres de forma privada; no mandarla por chat ni publicarla. El agente puede generar SESSION_SECRET aleatorio sin imprimirlo y cargarlo como variable sellada cuando exista el servicio autorizado. scripts/generate_session_secret.py es el procedimiento local de respaldo; su archivo exclusivo 0600 debe quedar fuera del repositorio y no conservarse en logs. Mantener secreto estable entre reinicios y custodiarlo privadamente.

Configurar DATABASE_URL como referencia privada al servicio exclusivo, PHOTO_DIR=/data/private-photos, COOKIE_SECURE=true, PUBLIC_REPORTS_ENABLED=false. PORT y RAILWAY_VOLUME_MOUNT_PATH los aporta Railway: no falsear el mount. No copiar valores ni contraseñas de otros proyectos. No hay contraseña definitiva elegida por el agente.

### 3. Despliegue controlado

Requiere autorización expresa distinta de construir código. Mantener PR sin fusionar hasta autorización de integración. Fuente/commit elegido expresamente, Dockerfile actual, healthcheck /health, timeout 120 s, política de reinicio ante fallo. No usar predeploy para fotos: el volumen se monta en runtime. Aplicar migraciones idempotentes al arranque bajo bloqueo. Observar estado final exitoso, no solo build queued. Generar dominio gratuito *.up.railway.app cuando se autorice exponer la prueba cerrada; verificar HTTPS/certificado y cookie Secure antes del acceso propietario.

Confirmar /api/config enabled=false y POST /api/reports 503 sin datos personales. Solo crear reportes sintéticos en ensayo aislado autorizado, nunca abrir recepción real para probar. Validar una conexión DB real, reinicio/redeploy y conservación de fotos. Comprobar rate limit tras proxy sin confiar en cabeceras arbitrarias; todos los cambios requieren CSRF y sesión revocable.

### 4. Respaldos y verificación

Política propuesta (todavía no activada): diario/6 días y semanal/27 días para ambos volúmenes. Revisar costos y retención antes de activar; monthly/89 días no concuerda con propuesta máxima de 30 días. Detener envíos y modificaciones administrativas para un corte coherente. Verificar backup creado con fecha/estado e intentar restauración en ensayo descartable autorizado. Registrar resultados verificables: conteos, fotos, bytes, PDF y Excel; un snapshot listado sin ensayo no es respaldo recuperable certificado.

Custodiar el registro reciente de eliminaciones fuera del snapshot a restaurar; descargarlo después de cada lote de borrados. Copias antiguas y exports privados vencen con la política aprobada, no por el borrado del sistema activo. No contratar almacenamiento externo sin autorización.

### 5. Recuperación

Recepción cerrada y acceso restringido. Conservar registro de eliminaciones más reciente antes de restaurar. Recuperar DB/fotos con corte coherente, invalidar sesiones y rotar contraseña privada si procede. Comparar referencias con archivos; reaplicar IDs del registro mediante el DELETE privado existente y verificar cola vacía/fotos borradas. No reabrir con discrepancias ni pérdida del registro mínimo. Los backups Railway solo se restauran en el mismo proyecto/entorno y conservan volumen anterior desmontado; su sustitución/redeploy necesita autorización. Ensayo aislado: copias lógicas y fotos descartables, como CI.

### 6. Activación posterior de recepción

Solo tras autorización explícita de lanzamiento, infraestructura y respaldos comprobados y pruebas físicas resueltas. El agente cambia PUBLIC_REPORTS_ENABLED=true exclusivamente en ReportaPA, verifica configuración y comportamiento esperado y conserva posibilidad de cierre inmediato mediante false. No se ejecutó esta fase ni se autoriza por aprobar el PR o el presupuesto.

## Estado del trabajo técnico antes de pruebas físicas

Los defectos corregibles detectados en esta auditoría se repararon y entraron a pruebas. No se requieren nuevas funcionalidades. Pendiente técnico no físico: confirmar plan/facturación, autorizar recursos y despliegue, provisionar infraestructura exclusiva, cargar secretos privados, verificar HTTPS/proxy/volumen real y crear/recuperar respaldos reales. Esos elementos son bloqueos de acceso/infraestructura/autorización, no se presentan como terminados. El run CI final y commit se registran en el informe del PR #1.

## Fuentes y documentos de operación

- https://docs.railway.com/pricing
- https://docs.railway.com/pricing/cost-control
- https://docs.railway.com/volumes/reference
- https://docs.railway.com/volumes/backups
- [Preparación de infraestructura](preproduccion-infraestructura.md)
- [Producción y pruebas físicas](produccion-y-pruebas.md)
- [Conservación y recuperación](conservacion-y-recuperacion.md)
