# ReportaPA 🇵🇦

Plataforma ciudadana gratuita e independiente para registrar daños en viviendas causados por sismos en Panamá.

## Alcance inicial
- Formulario móvil sin cuenta para ciudadanos.
- Provincia, distrito, corregimiento y comunidad.
- Enlace compartido de Google Maps (sin exigir coordenadas).
- Descripción de afectaciones y hasta tres fotografías.
- Número de seguimiento por reporte.
- Panel privado del administrador: filtros, estados, fotografías, enlaces Maps y exportación CSV compatible con Excel.
- Listado público únicamente con datos agregados y sin ubicación exacta ni datos personales.

## Privacidad y seguridad
Los nombres, teléfonos, fotografías privadas y ubicaciones exactas solo serán accesibles para personal autorizado. No almacenar secretos ni datos personales en el repositorio. Validar enlaces, archivos y entradas; limitar solicitudes y prevenir registros duplicados. Las credenciales se configuran en variables de entorno de Railway.

## Aviso
Iniciativa ciudadana independiente. No es un canal oficial de emergencias, no garantiza inspecciones ni asistencia. Ante peligro inmediato, contactar a las autoridades de emergencia.

## Estado
Inicio del proyecto. La aplicación, el panel y la infraestructura aún deben implementarse y verificarse antes de abrir el registro público.

## MVP implementado (rama de trabajo)
Una aplicación FastAPI sirve el formulario, API y panel privado. PostgreSQL es la única fuente de reportes; las fotos se guardan en un volumen privado y se entregan únicamente mediante rutas administrativas autenticadas. Las exportaciones definitivas son `.xlsx` (sustituyen CSV), además de PDF agregado y Excel anonimizado. No se incluyen fotografías ni enlaces públicos de fotografías en exportaciones.

### Ejecución y configuración
Python 3.12: `pip install -r requirements.txt`; configurar las variables de `.env.example` en el entorno (no se carga `.env` automáticamente) y ejecutar `uvicorn app.main:app`. La aplicación aplica la migración idempotente al iniciar. PostgreSQL debe ser exclusivo de ReportaPA. `PHOTO_DIR` debe apuntar a un volumen persistente privado montado en `/data`; no usar el filesystem efímero de un servicio para fotografías reales. Respaldar conjuntamente PostgreSQL y el volumen. No existe publicación automática en esta rama.

`ADMIN_PASSWORD` debe tener al menos 16 caracteres y `SESSION_SECRET` al menos 32; generar valores aleatorios independientes. El panel está en `/admin`; la cookie expira en una hora y exige HTTPS por defecto. `COOKIE_SECURE=false` solo para pruebas locales. La recepción está cerrada por defecto con `PUBLIC_REPORTS_ENABLED=false`; cambiarla requiere autorización de lanzamiento.

### Verificación
`pip install pytest httpx`; `python -m pytest -q`. Las pruebas de integración necesitan `DATABASE_URL` apuntando a una base **de pruebas descartable**, pues vacían sus tablas. GitHub Actions ejecuta toda la suite con PostgreSQL 16 aislado. Los tests nunca utilizan registros reales.

### Límites y pendientes de operación
Antes del lanzamiento: aprovisionar PostgreSQL y volumen exclusivos, configurar secretos/HTTPS/backups, verificar cookies y fotos en dispositivos Android/iPhone/tablet, y autorizar explícitamente recepción pública. Los enlaces Maps cortos se guardan sin seguir redirecciones: el detector de duplicados compara teléfono normalizado y enlace idéntico; diferentes enlaces de una misma vivienda requieren revisión humana. No se bloquean reportes de daños nuevos o de otras familias. El nombre y los campos territoriales no se verifican contra un padrón oficial. La sesión es para un único administrador; no se creó un sistema paralelo de cuentas.

El volumen y la transacción SQL no comparten una transacción distribuida. Se eliminan archivos si el guardado falla; un cierre abrupto podría dejar fotos huérfanas privadas que requieren revisión de mantenimiento. En la escala inicial, las exportaciones se generan en memoria y los filtros comparan textos exactos.

### Seguimiento de ayuda por WhatsApp
El panel ofrece «Consultar ayuda por WhatsApp» por reporte. Solo una acción explícita abre `wa.me` con el teléfono normalizado con +507 y el mensaje aprobado. El administrador revisa y envía manualmente; abrir WhatsApp no guarda un estado ni afirma que el mensaje fue enviado. No hay WhatsApp Business API, bots, cobros ni envío automático. El número de WhatsApp no se valida como cuenta activa: eso lo determina la aplicación de WhatsApp.

La migración `002_help_followup.sql` añade al mismo reporte `estado_ayuda`, fecha, observación de hasta 500 caracteres, administrador e historial JSONB. Es idempotente y conserva los reportes existentes como «Pendiente de confirmar», sin inventar una fecha previa. El estado operativo sigue independiente. El historial se agrega transaccionalmente bajo bloqueo del reporte; repetir exactamente un guardado no duplica eventos. La autenticación por contraseña compartida no identifica personas: administrador se mantiene nulo, sin atribuciones inventadas.

Los filtros y Excel incorporan el estado de ayuda y la fecha. La observación y el historial son privados; el Excel anonimizado omite las observaciones. La ficha PDF individual, distinta del resumen agregado, se descarga desde cada caso y requiere sesión. Incluye información privada, estado/fecha de ayuda y hasta tres fotos, en una sola página A4; ajusta el bloque de texto para acomodar descripciones extensas. No compartirla como si fuera el PDF anonimizado.

Pruebas adicionales: `node --test tests/test_followup.js`; instalar `pypdf==5.9.0` junto con pytest/httpx para verificar páginas e imágenes PDF. Pendientes físicos: apertura de WhatsApp en Android, iPhone y tablet, revisión del número/texto en el compositor, envío manual, estado sin cambios al abrir, guardado tras respuesta, filtros y descargas Excel/PDF. Recepción pública continúa cerrada.
