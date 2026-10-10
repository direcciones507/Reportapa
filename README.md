# ReportaPA 🇵🇦

Plataforma ciudadana gratuita e independiente para registrar daños en viviendas causados por sismos en Panamá.

## Alcance inicial
- Formulario móvil sin cuenta para ciudadanos.
- Provincia, distrito, corregimiento y comunidad.
- Enlace compartido de Google Maps (sin exigir coordenadas).
- Descripción de afectaciones y hasta tres fotografías.
- Número de seguimiento por reporte.
- Panel privado del administrador: filtros, estados, fotografías, enlaces Maps y exportaciones Excel .xlsx.
- Exportación anonimizada desde el panel privado; no hay listado público habilitado.

## Privacidad y seguridad
Los nombres, teléfonos, fotografías privadas y ubicaciones exactas solo serán accesibles para personal autorizado. No almacenar secretos ni datos personales en el repositorio. Validar enlaces, archivos y entradas; limitar solicitudes y prevenir registros duplicados. Las credenciales se configuran en variables de entorno de Railway.

## Aviso
Iniciativa ciudadana independiente. No es un canal oficial de emergencias, no garantiza inspecciones ni asistencia. Ante peligro inmediato, contactar a las autoridades de emergencia.

## Estado
MVP implementado en el PR #1, pendiente de integración autorizada, infraestructura y pruebas físicas. Recepción pública cerrada por defecto.

## MVP implementado (rama de trabajo)
Una aplicación FastAPI sirve el formulario, API y panel privado. PostgreSQL es la única fuente de reportes; las fotos se guardan en un volumen privado y se entregan únicamente mediante rutas administrativas autenticadas. Las exportaciones definitivas son `.xlsx` (sustituyen CSV), además de PDF agregado y Excel anonimizado. No se incluyen fotografías ni enlaces públicos de fotografías en exportaciones.

### Ejecución y configuración
Python 3.12: `pip install -r requirements.txt`; configurar las variables de `.env.example` en el entorno (no se carga `.env` automáticamente) y ejecutar `uvicorn app.main:app`. La aplicación aplica las migraciones idempotentes al iniciar, bajo bloqueo PostgreSQL para evitar arranques simultáneos. PostgreSQL debe ser exclusivo de ReportaPA. `PHOTO_DIR` debe apuntar a un volumen persistente privado montado en `/data`; no usar el filesystem efímero de un servicio para fotografías reales. Respaldar conjuntamente PostgreSQL y el volumen. No existe publicación automática en esta rama.

`ADMIN_PASSWORD` debe tener al menos 16 caracteres y `SESSION_SECRET` al menos 32; el propietario proporciona la contraseña privada y SESSION_SECRET se genera de forma criptográfica e independiente. El propietario ingresa en `/admin` con usuario `Ayudapanama` y la contraseña privada de `ADMIN_PASSWORD`; la cookie expira en una hora y exige HTTPS por defecto. `COOKIE_SECURE=false` solo para pruebas locales. La recepción está cerrada por defecto con `PUBLIC_REPORTS_ENABLED=false`; cambiarla requiere autorización de lanzamiento.

### Verificación
`pip install pytest httpx`; `python -m pytest -q`. Las pruebas de integración requieren `DATABASE_URL` en localhost/127.0.0.1 con nombre `reportapa_test`, **base descartable**, pues vacían sus tablas. Rechazan otras bases antes de cambiar datos. GitHub Actions ejecuta toda la suite con PostgreSQL 16 aislado. Los tests nunca utilizan registros reales.

### Límites y pendientes de operación
Antes del lanzamiento: aprovisionar PostgreSQL y volumen exclusivos, configurar secretos/HTTPS/backups, verificar cookies y fotos en dispositivos Android/iPhone/tablet, y autorizar explícitamente recepción pública. Los enlaces Maps cortos se guardan sin seguir redirecciones: el detector compara teléfono/familia con enlace, sector y coordenadas explícitas disponibles; coincidencias ambiguas requieren revisión humana. No se bloquean reportes de daños nuevos o de otras familias. El nombre y los campos territoriales no se verifican contra un padrón oficial. La sesión es para un único administrador; no se creó un sistema paralelo de cuentas.

El volumen y la transacción SQL no comparten una transacción distribuida. Se eliminan archivos si el guardado falla; un cierre abrupto podría dejar fotos huérfanas privadas que requieren revisión de mantenimiento. En la escala inicial, las exportaciones se generan en memoria y los filtros comparan textos exactos.

### Seguimiento de ayuda por WhatsApp
El panel ofrece «Consultar ayuda por WhatsApp» por reporte. Solo una acción explícita abre `wa.me` con el teléfono normalizado con +507 y el mensaje aprobado. El administrador revisa y envía manualmente; abrir WhatsApp no guarda un estado ni afirma que el mensaje fue enviado. No hay WhatsApp Business API, bots, cobros ni envío automático. El número de WhatsApp no se valida como cuenta activa: eso lo determina la aplicación de WhatsApp.

La migración `002_help_followup.sql` añade al mismo reporte `estado_ayuda`, fecha, observación de hasta 500 caracteres, administrador e historial JSONB. Es idempotente y conserva los reportes existentes como «Pendiente de confirmar», sin inventar una fecha previa. El estado operativo sigue independiente. El historial se agrega transaccionalmente bajo bloqueo del reporte; repetir exactamente un guardado no duplica eventos. El acceso exclusivo del propietario identifica al usuario `Ayudapanama` en los seguimientos nuevos. Los cambios antiguos conservan su administrador nulo, sin atribuciones retroactivas.

Los filtros y Excel incorporan el estado de ayuda y la fecha. La observación y el historial son privados; el Excel anonimizado omite las observaciones. La ficha PDF individual, distinta del resumen agregado, se descarga desde cada caso y requiere sesión. Incluye información privada, estado/fecha de ayuda y hasta tres fotos, en una sola página A4; ajusta el bloque de texto para acomodar descripciones extensas. No compartirla como si fuera el PDF anonimizado.

Pruebas adicionales: `node --test tests/test_followup.js`; instalar `pypdf==5.9.0` junto con pytest/httpx para verificar páginas e imágenes PDF. Pendientes físicos: apertura de WhatsApp en Android, iPhone y tablet, revisión del número/texto en el compositor, envío manual, estado sin cambios al abrir, guardado tras respuesta, filtros y descargas Excel/PDF. Recepción pública continúa cerrada.

### Acceso exclusivo y preparación de producción
Se conserva el mismo login, cookie firmada y rutas privadas, ahora con usuario obligatorio `Ayudapanama`. La migración `003_owner_sessions.sql` añade revocación de sesiones a la misma base; no crea cuentas, registro ni una segunda autenticación. Cerrar sesión invalida la sesión en el servidor, incluso si se conserva una copia de la cookie. Cambiar `ADMIN_PASSWORD` invalida las sesiones emitidas con la contraseña anterior. Las cookies son HttpOnly, SameSite=Strict y Secure por defecto; los cambios requieren CSRF; el acceso bloquea más de 10 intentos en 15 minutos.

En Railway, el arranque exige un `PHOTO_DIR` dentro del volumen persistente indicado por `RAILWAY_VOLUME_MOUNT_PATH` y cookies seguras. El Dockerfile usa `exec` para propagar señales al servidor. Configuración y checklist: [Producción y pruebas físicas](docs/produccion-y-pruebas.md). Ningún secreto está incluido en el código o documentos.

### Hogar, ubicación y ciclo de vida del reporte
La migración `004_household_lifecycle.sql` conserva la tabla de reportes, añade archivo y claves de coincidencia, y dos registros operativos mínimos para limpieza de fotos y tratamiento de eliminaciones en respaldos. Los datos agregados del hogar se guardan en el JSON existente; antiguos quedan sin cantidades inventadas. La API valida edades no superpuestas y total, distingue cero de campo omitido y no suma discapacidad dos veces. Google Maps mantiene el enlace original y solo extrae coordenadas explícitas de un lugar o búsqueda numérica; no resuelve enlaces cortos ni trata la vista `@` como vivienda.

Los reintentos con la misma clave conservan su ID. Reenvíos exactamente iguales con otra clave se rechazan sin revelar IDs; coincidencias por teléfono, familia, sector o coordenadas advierten sin datos personales y permiten confirmar familias diferentes o daños nuevos. No se promete identificar todas las variantes de enlaces o nombres. Archivar conserva todo; eliminación exige confirmación privada y limpieza física recuperable tras fallos. [Conservación y recuperación](docs/conservacion-y-recuperacion.md) define respaldos, registro mínimo de borrados, límites y pruebas de recuperación.

### Cierre técnico y operación
[Auditoría de cierre y operación](docs/cierre-tecnico-y-operacion.md) reúne pendientes clasificados, presupuesto objetivo de USD 10 adicionales (sin autorización de contratación), activación, monitoreo y condiciones de lanzamiento. Los cuatro documentos originales conservan el bloque aprobado; este README y los informes posteriores reflejan lo realmente implementado.
