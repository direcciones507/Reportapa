# Flujo de envío y prevención de duplicados

## Acceso ciudadano
Formulario público y gratuito, sin correo electrónico, cuenta ni contraseña.

## Envío
1. Validar campos obligatorios, enlace Google Maps y fotografías.
2. Aplicar límites de solicitudes y controles antispam.
3. Buscar posibles duplicados con teléfono normalizado y ubicación (y otros indicios); no depender solo del teléfono porque varias familias pueden compartirlo.
4. Si se confirma un reporte nuevo, guardar transaccionalmente y generar identificador RPA correlativo único.
5. Mostrar pantalla de éxito con número de reporte, aviso de que no garantiza ayuda y botón "Volver al inicio".
6. Evitar doble envío por repetición de clics o reintentos con clave de idempotencia.
7. Si hay coincidencia probable, no exponer datos de otros reportes ni afirmar que el reporte pertenece a quien envía el formulario. Ofrecer revisión o mecanismo de recuperación verificado; permitir reportar daños nuevos.

## Panel
Solo administrador autenticado; ver y filtrar reportes y descargar máster Excel o Excel por área.

## Estado
Requisito funcional documentado, pendiente de implementación y pruebas.
