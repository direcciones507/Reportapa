# Ajuste del PR #2: una fotografía opcional y prioridad del registro

Continúa el commit 06378aad49e242675c99cb50090f7287349d88b2. No cambia el pool (máximo 8 conexiones), la admisión acotada, los controles de abuso por teléfono ni los bloqueos transaccionales para idempotencia y duplicados.

## Comportamiento

- Nuevos reportes: cero o una fotografía, hasta 5 MiB, formatos JPEG/PNG/WebP. Se conserva el procesamiento privado existente.
- Históricos: las listas de dos o tres fotografías, el acceso privado y los PDF permanecen compatibles. No se recortan ni reescriben los archivos históricos.
- Espacio insuficiente (reserva de 32 MiB), disco lleno, cuota, falta de permisos y errores de escritura/sincronización: el reporte se confirma en PostgreSQL con `photos=[]`. La respuesta y la pantalla de éxito incluyen exactamente: **No se puede subir la foto en este momento, pero puedes seguir con tu reporte.**
- Solo se eliminan archivos parciales creados por el intento fallido. Si no se pueden eliminar, se utiliza la cola de limpieza existente. Nunca se sobrescribe un archivo: creación exclusiva con UUID y permisos 0600.
- La migración 005 añade una marca de fallo, sin cambiar datos familiares ni listas históricas. Reintentar con la misma clave, con la foto original o sin ella, devuelve el mismo número. Cambiar los datos familiares con esa clave sigue dando conflicto.
- La confirmación requiere COMMIT en PostgreSQL o una consulta que verifique su resultado. Una caída de PostgreSQL sigue siendo un error recuperable; nunca se confirma un reporte no guardado.
- El arranque y el envío sin foto toleran fallos de acceso al directorio privado. Se conserva la validación de configuración y montaje persistente de Railway, evitando escribir fotos en un montaje incorrecto.
- El diagnóstico interno registra etapa y errno; no incluye contenido familiar ni expone rutas o errores técnicos al ciudadano.

## Crecimiento y panel existente

No hay un límite acumulado de reportes. Los límites de seguridad son por intentos y recursos simultáneos. La secuencia sigue creciendo y los números de más de ocho cifras ya no se truncarán. La paginación consulta COUNT y LIMIT 20/OFFSET en PostgreSQL, en lugar de materializar todos los registros.

El panel privado consulta `/api/admin/storage`, protegido por la autenticación administrativa existente. Muestra el COUNT real de todos los reportes (incluidos archivados), el número real de archivos JPEG privados, bytes ocupados/disponibles del sistema de archivos montado y alertas a 70%, 85% y 95%. Los bytes son del volumen completo, no únicamente de las fotografías; la ocupación incluye espacio no disponible para escribir. Los archivos privados pendientes de limpieza también se cuentan mientras existan. Si la lectura falla, los datos de almacenamiento son nulos/indisponibles, nunca ceros inventados. Actualización al iniciar sesión y mediante el botón del panel; no se ejecuta un escaneo masivo en cada solicitud pública.

## Ampliación autorizada del volumen existente

Verificado por lectura de Railway: volumen `reportapa-private-data`, ID `4057b02a-43c4-48c6-8b75-3466a673b38d`, montado en `/data`, tamaño 1024 MB. No se ha cambiado.

El conector disponible permite cambiar nombre/montaje/asociación, **no permite cambiar tamaño**. No debe utilizarse para simular una ampliación ni provocar un redeploy.

Paso desde la tableta: Railway → proyecto **ReportaPA** → entorno **production** → pulsar el volumen existente **reportapa-private-data** → **Live Resize** → indicar **20 GB** → revisar el importe y confirmar. Mantener el mismo volumen y `/data`. Después verificar que aparezcan 20 GB y, una vez autorizados/desplegados estos cambios, actualizar los indicadores del panel para comprobar el espacio real.

Documentación oficial: https://docs.railway.com/volumes#live-resizing-the-volume. Railway documenta ampliación en vivo sin interrupción; un volumen al 100% puede requerir ampliación offline con breve reinicio para comprobaciones de integridad. Si la pantalla propone cambiar el montaje o reemplazar el volumen, detenerse.

Precio oficial de referencia: https://docs.railway.com/pricing, US$0.15/GB/mes. 20 GB utilizados equivalen aproximadamente a US$3/mes de almacenamiento; aumento máximo respecto a 1 GB utilizado: US$2.85/mes. No incluye cómputo ni red ni cambios de plan. No se han contratado recursos adicionales.

## Validación reproducible

`python -m pytest -q`, `node --check app/static/citizen.js`, `node --check app/static/admin.js`, `node --test tests/test_*.js`, `docker build --tag reportapa-ci .`, `python scripts/load_capacity.py`.

CI utiliza PostgreSQL 16 desechable y directorios privados temporales independientes. Las pruebas de integración rechazan cualquier DATABASE_URL que no sea localhost y `reportapa_test`. Incluyen 30.000 registros sintéticos más un envío ciudadano, persistencia tras COMMIT, recuperación de respaldo y reinicios, fallos de almacenamiento, reintentos, conservación histórica y autenticación/exportaciones. Nunca se ejecutan sobre producción.

La carga progresiva anterior con tres fotos corresponde al protocolo anterior. Este ajuste vuelve a medir navegación, envíos sin foto y envíos con **una** foto, con los mismos umbrales y cortes automáticos. Los resultados se publican en el artefacto de GitHub Actions `reportapa-capacity-results`; no representan capacidad validada en Railway producción ni ocupación real de sus archivos.

Pendiente: resultados del CI de este ajuste, ampliación manual verificada y autorización posterior de merge/despliegue. No declarar producción apta para miles de usuarios a partir de las pruebas de este runner.
