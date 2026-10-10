# Preproducción e infraestructura exclusiva de ReportaPA

Auditoría del 10 de octubre de 2026. Alcance: repositorio Reportapa, rama feat/reportapa-mvp-20261010, PR #1. No se fusiona, despliega, conecta una fuente con despliegue automático ni abre recepción ciudadana. PUBLIC_REPORTS_ENABLED=false en la configuración propuesta y en CI, excepto fixtures locales aisladas que prueban envíos descartables.

## Inventario y bloqueo de costos

Lectura del inventario Railway: siete proyectos accesibles. Ninguno llamado ReportaPA. Los cuatro proyectos de nombre genérico se revisaron solo por inventario/fuente en su entorno production: meticulous-elegance contiene LeveIA; amused-enchantment contiene Direcciones507/n8n/Postgres; magnificent-abundance y clever-patience no tienen servicios en ese entorno. Los tres proyectos identificados por nombre como Empleos/LeveIA no se reutilizan. No se prueba la ausencia de recursos en todos los entornos posibles; no se encontró uno identificable como ReportaPA. No se consultaron valores secretos ni se modificó ningún proyecto.

Recursos Railway creados: ninguno. Costos nuevos contratados: ninguno. No existe enlace provisional verificado de ReportaPA. El subdominio *.up.railway.app se generará únicamente después de autorizar un despliegue de prueba; no se compra dominio.

El plan Free admite un volumen por proyecto; esta arquitectura necesita dos. No se presupone un plan o saldo suficiente de la cuenta. La facturación oficial consultada indica Hobby desde USD 5/mes, Pro desde USD 20/mes, incluyendo crédito de consumo, no una garantía de costo fijo para dos servicios. RAM USD 10/GB-mes, CPU USD 20/vCPU-mes, egreso USD 0.05/GB y almacenamiento usado USD 0.15/GB-mes. Backups incrementales se cobran como volumen por sus datos exclusivos. Debe aprobarse el presupuesto antes de provisionar servicios, volúmenes o respaldos; no usar créditos existentes como autorización de gasto.

## Configuración concreta preparada, todavía no aplicada

| Recurso | Configuración |
| --- | --- |
| Proyecto nuevo | ReportaPA, exclusivo, región única elegida por propietario |
| Servicio PostgreSQL | Postgres dedicado con su volumen propio; red privada, sin TCP proxy público; versión compatible con las migraciones, validada en CI con PostgreSQL 16 |
| Servicio web | Dockerfile actual, una instancia, CMD existente, healthcheck /health (120 s), reinicio ante fallo |
| Fuente | Solo Reportapa; conectar únicamente en fase de despliegue autorizada, pues la conexión puede construir/desplegar inmediatamente |
| Fotos | Volumen exclusivo de web en /data, PHOTO_DIR=/data/private-photos; ninguna ruta estática al volumen |
| HTTPS | Dominio Railway gratuito y certificado válido; comprobar antes del login. No configurar hostname inventado |
| Variables | DATABASE_URL referencia al Postgres exclusivo; ADMIN_PASSWORD privada del propietario; SESSION_SECRET privado estable; COOKIE_SECURE=true; PUBLIC_REPORTS_ENABLED=false |

No usar replicas con volumen local. Railway permite un volumen por servicio; la base y la web tienen volúmenes separados. Los despliegues con volumen pueden producir una breve interrupción. Mantener las comprobaciones de arranque: PHOTO_DIR debe estar dentro de RAILWAY_VOLUME_MOUNT_PATH real, cookies seguras y secretos de longitud suficiente. Variables completas y checklist en [produccion-y-pruebas.md](produccion-y-pruebas.md).

## Capacidad fotográfica

Hasta tres archivos de entrada de 5 MiB, convertidos a JPEG sin metadatos, máximo 2000 px por lado. La ocupación final debe medirse; la compresión no promete una razón fija. Presupuesto ilustrativo conservador de planificación de 15 MiB por reporte: unos 341 reportes ocuparían 5 GiB antes de metadatos, margen libre y backups. No es una cuota técnica ni una capacidad garantizada. Reservar al menos 20% libre y revisar uso real; backups manuales Railway tienen un límite documentado del 50% del volumen. Volúmenes por defecto: Free/Trial 0.5 GB, Hobby 5 GB, Pro 50 GB; verificar plan y capacidad seleccionados antes de crear.

Las fotos requieren sesión y referencia vigente en PostgreSQL. Borrado definitivo retira acceso inmediatamente y usa la cola SQL existente para reintentar eliminación física al inicio y cada 30 segundos. La prueba de recuperación verifica hashes mediante igualdad exacta de bytes. Persistencia en un directorio de CI no certifica un volumen Railway ni un nuevo despliegue en esa plataforma.

## Procedimiento privado de secretos

No se generó ni estableció contraseña definitiva. El propietario proporciona ADMIN_PASSWORD, única y de al menos 16 caracteres, como variable sellada; no enviarla por chat. Para SESSION_SECRET ejecutar localmente:

```sh
python scripts/generate_session_secret.py --output /ruta/privada/fuera-del-repositorio/session.env
```

El script usa aleatoriedad criptográfica, crea exclusivamente un archivo modo 0600, rechaza sobrescritura y no imprime el secreto. Importar su único valor como variable sellada de Railway y custodiarlo en un gestor privado. No ejecutar con shell tracing, no adjuntar el archivo a informes y no subirlo a GitHub. No se han generado secretos de producción durante esta auditoría. Rotar SESSION_SECRET altera sesiones y coincidencias de duplicados; mantenerlo estable entre reinicios. El ensayo automatizado genera solo un secreto descartable en directorio temporal.

## Respaldos propuestos para aprobación

PostgreSQL y fotos: respaldos diarios (retención nativa 6 días) y semanales (27 días) en sus dos volúmenes. No habilitar mensuales (89 días) sin revisar la propuesta máxima de 30 días de conservación. Estos calendarios no están activados. Costos incrementales dependen de cambios reales; no prometer un precio total sin medición. La copia lógica y la copia fotográfica deben tener un corte coherente con envíos cerrados y modificaciones administrativas detenidas.

Registro mínimo de eliminaciones: descargar export privado después de cada lote de eliminaciones y antes de restaurar; custodiar copia reciente fuera del snapshot que se restaurará, con acceso del propietario. Su copia incluida en un backup antiguo no sustituye la más reciente. Mantenerlo mientras existan backups capaces de reintroducir esos IDs. No se contrató almacenamiento externo. Restauraciones nativas Railway conservan el volumen anterior desmontado y sus backups más nuevos; revisar su retención y acceso, no afirmar que desaparecieron automáticamente.

Recuperación: restaurar DB/fotos aisladas, invalidar sesiones, comprobar referencias y reaplicar el registro reciente con la misma API privada de eliminación antes de devolver acceso. Detalle en [conservacion-y-recuperacion.md](conservacion-y-recuperacion.md). Un backup solo se considerará operativo tras crear y recuperar una copia en infraestructura autorizada.

## Ensayo automático añadido

CI usa PostgreSQL 16 descartable, sin datos reales. La recuperación requiere REPORTAPA_RECOVERY_TEST=disposable-ci, host localhost/127.0.0.1 y base reportapa_test; no se ejecuta contra DATABASE_URL de producción. Crea un reporte sintético, toma pg_dump custom y copia de fotos, elimina el caso, exporta el registro reciente, restaura con pg_restore en otra base temporal y copia de fotos independiente, invalida sesiones, reinicia la aplicación dos veces y dos procesos Uvicorn reales sobre loopback privado, verifica migraciones repetidas, seguimiento, privacidad, Excel y PDF individual de una página. Reaplica eliminaciones y comprueba retirada física. Borra la base temporal de ensayo al terminar. No publica archivos de respaldo como artefactos de CI. También construye el Dockerfile sin publicar la imagen ni desplegarla.

Otra prueba usa recepción cerrada, sesión con cookie segura sobre URL HTTPS simulada, login incorrecto, login correcto, logout y rechazo del token revocado. Esta simulación no prueba certificado ni proxy reales. El script de secretos se prueba por permisos, longitud, silencio y rechazo de sobrescritura. Los resultados exactos quedan en el informe y el run CI del PR.

## Intervenciones imprescindibles y límites

1. Autorizar presupuesto y creación de un proyecto exclusivo y sus dos servicios/volúmenes. Si hay un ReportaPA bajo otro nombre/entorno, identificarlo antes de crear.
2. Autorizar por separado el despliegue cerrado y subdominio gratuito; aportar contraseña privada y decidir región/capacidad/retención. No requiere integrar el PR para aprobar infraestructura.
3. Luego probar volumen real tras reinicio y nuevo despliegue, HTTPS/cookie/proxy, backups y recuperación real descartable; mantener recepción cerrada.
4. Android, iPhone y tablet: login/logout y bloqueo de URLs privadas; WhatsApp manual +507; filtro/historial; Excel privado/anonimizado; PDF de una página con tres fotos; archivo y eliminación con confirmación. Formulario solo en ensayo aislado autorizado.

No se solicita autorización de recepción pública ni de integración en este procedimiento. Revisar ambos por separado cuando corresponda.

## Fuentes oficiales consultadas

- https://docs.railway.com/pricing
- https://docs.railway.com/volumes/reference
- https://docs.railway.com/volumes/backups
