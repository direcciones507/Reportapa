# ReportaPA: preparación de producción y pruebas físicas

## Estado real y alcance de la auditoría

El código está preparado en el PR #1; no se fusionó, desplegó ni abrió recepción pública. La consulta de lectura al inventario de Railway no encontró un proyecto llamado ReportaPA. Hay proyectos con nombres genéricos: no se les atribuye ReportaPA sin evidencia ni se inspeccionan/modifican servicios de otros proyectos. El propietario debe identificar un proyecto/servicio dedicado si ya existe o autorizar su creación posteriormente. No se crearon ni contrataron recursos.

El acceso del propietario usa exclusivamente `Ayudapanama` y una contraseña privada, sin Google, correo ni registro. Las migraciones siguen aplicándose de forma idempotente al iniciar el mismo servicio: 001 reportes, 002 seguimiento de ayuda, 003 revocación de sesiones. No se crea otra base de datos ni otro sistema de acceso.

## Configuración preparada para Railway

Una aplicación web/API integrada desde el Dockerfile del repositorio, PostgreSQL dedicado y volumen privado persistente de fotografías. Al configurar posteriormente:

- Fuente: este repositorio, raíz `/`; seleccionar `main` solo después de integrar con autorización. No conectar la rama de trabajo a publicación automática.
- Constructor: Dockerfile existente. Comando de inicio: el CMD del Dockerfile, que escucha en `0.0.0.0` y `PORT` proporcionado por Railway. No escribir un puerto distinto en el dominio.
- Healthcheck: `/health`, timeout sugerido 120 segundos; consulta PostgreSQL. No contiene datos privados.
- Una réplica para el MVP con volumen local, una región y reinicio ante fallo. No habilitar réplicas múltiples que no compartan las fotos.
- Volumen de la aplicación montado en `/data`; `PHOTO_DIR=/data/private-photos`. PostgreSQL requiere su propio volumen persistente. Las fotos nunca se sirven como archivos estáticos.
- No usar un pre-deploy para manipular fotos: los volúmenes están disponibles en ejecución. Las migraciones actuales se aplican al arranque.
- Mantener la recepción cerrada. Primero verificar un despliegue autorizado saludable, sesión y almacenamiento; luego pruebas aisladas sin datos reales. La recepción real requiere autorización separada.

La documentación oficial consultada el 10-10-2026 indica que nuevos servicios ya no pueden optar por `railway.json`/`railway.toml`; por eso no se añade una configuración obsoleta. Los parámetros anteriores pueden configurarse en el panel en la fase autorizada. No se ejecutó ninguna operación de despliegue.

## Valores y decisiones del propietario

| Variable/configuración | Valor o decisión requerida |
| --- | --- |
| Usuario propietario | `Ayudapanama`, fijo; no se requiere otra variable ni cuenta |
| `ADMIN_PASSWORD` | Contraseña única privada, mínimo 16 caracteres; configurar como variable sellada |
| `SESSION_SECRET` | Secreto aleatorio independiente, mínimo 32 caracteres; sellado y estable entre reinicios |
| `DATABASE_URL` | Referencia privada al PostgreSQL exclusivo: `${{Postgres.DATABASE_URL}}`, ajustando `Postgres` al nombre real del servicio |
| `PHOTO_DIR` | `/data/private-photos` dentro del volumen de la aplicación |
| `COOKIE_SECURE` | `true` en producción |
| `PUBLIC_REPORTS_ENABLED` | `false`; no cambiar sin autorización de lanzamiento |
| `PORT` | Lo proporciona Railway; no requiere valor privado del propietario |
| `RAILWAY_VOLUME_MOUNT_PATH` | Lo proporciona Railway cuando el volumen está montado; no inventarlo para eludir la comprobación |
| Proyecto/servicio/región | Identificar uno exclusivo o autorizar su creación y costos posteriormente |
| Dominio | Elegir dominio de ReportaPA o dominio de Railway cuando se autorice publicar; HTTPS y certificado válidos antes del login |
| Respaldos | Aprobar frecuencia, retención, acceso y presupuesto para PostgreSQL y fotografías; comprobar restauración aislada |

No enviar contraseñas por chat ni incluirlas en el repositorio. No se generan secretos de producción en las pruebas. `SESSION_SECRET` también firma huellas de duplicados: mantenerlo estable y planificar su rotación, pues cambiarlo altera futuras coincidencias. Cambiar `ADMIN_PASSWORD` no altera esas huellas, pero invalida sesiones anteriores.

## Seguridad y límites comprobables antes de lanzamiento

- HTTPS en el dominio público de la aplicación; PostgreSQL por red privada, sin habilitar proxy público innecesario.
- No configurar CDN para cachear el panel, API privada, fotos o exportaciones; todas estas respuestas incluyen `Cache-Control: no-store`.
- Cookie administrativa con expiración de una hora, HttpOnly, Secure y SameSite=Strict. CSRF obligatorio en cambios y logout; logout revoca en PostgreSQL. No se almacena contraseña ni cookie en texto plano en la tabla de sesiones.
- La aplicación rechaza el arranque en Railway si las fotos quedan fuera del volumen declarado o si las cookies seguras están desactivadas. Esto es una comprobación de configuración; comprobar persistencia con un reinicio autorizado sigue siendo necesario.
- El límite de solicitudes usa el peer directo y no confía en cabeceras de IP arbitrarias. Antes de abrir recepción verificar el comportamiento del proxy de Railway: si comparte un peer, los límites podrían ser compartidos. No afirmar que el límite es por ciudadano hasta comprobarlo en infraestructura real.
- El mismo volumen y PostgreSQL no comparten transacción distribuida. Reinicios abruptos pueden dejar fotos huérfanas privadas; el respaldo y mantenimiento deben preservar las fotos referenciadas.

## Respaldos y restauración

Respaldar por separado PostgreSQL (reportes, seguimiento y sesiones) y el volumen privado de fotos. Las referencias de fotos viven en la base: mantener fechas de corte compatibles. Para una copia coherente, cerrar temporalmente el envío y evitar cambios administrativos durante la toma de ambos respaldos cuando se autorice esa operación. Elegir una política que permita recuperar tanto registros como imágenes; un volumen persistente solo no sustituye respaldo.

Verificar disponibilidad/costos de backups en el plan real antes de contratarlos. No se habilitaron backups ni se restauró nada en servicios reales durante este bloque. La primera restauración debe probarse en entorno aislado autorizado, con conteos, fotos privadas y PDF; nunca restaurar encima de otro proyecto.

## Checklist físico corto: Android, iPhone y tablet

Repetir en cada dispositivo, una vez autorizado el despliegue de prueba:

1. Abrir `/admin`: contraseña o usuario incorrecto rechaza; `Ayudapanama` y contraseña privada permiten entrar. No guardar secretos en capturas.
2. Comprobar formulario sin cuenta en pruebas aisladas autorizadas: registrar un caso de prueba, verificar número único, reintento sin doble registro y fotos privadas. La recepción real sigue cerrada.
3. Abrir WhatsApp desde el caso: destinatario +507 y texto correctos; el administrador revisa/envía manualmente; el estado sigue intacto hasta guardarlo. Número inválido muestra aviso.
4. Guardar estado/observación de ayuda; recargar, verificar historial, propietario y filtro por ayuda, sin alterar estado operativo.
5. Descargar Excel nacional/área y anonimizado: filtros y columnas correctos, sin teléfono/observación en anonimizado. Descargar ficha PDF: una página con hasta tres fotos; resumen sigue siendo separado.
6. Cerrar sesión: panel y URLs directas de fotos, Excel y PDF quedan protegidos. Reingresar y comprobar persistencia de reportes/fotos tras un reinicio de prueba autorizado.

## Referencias oficiales consultadas

- [Configuración de Railway](https://docs.railway.com/config-as-code)
- [Volúmenes y respaldos](https://docs.railway.com/volumes/reference)
- [Backup y restauración PostgreSQL](https://docs.railway.com/volumes/backups)
- [Conexión PostgreSQL](https://docs.railway.com/databases/postgresql)
