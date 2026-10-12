# Exportaciones Excel del panel administrativo

## Informes estadísticos preparados (12 de octubre de 2026)

La ampliación reutiliza el panel, la consulta de reportes y openpyxl existentes. No añade campos ciudadanos ni migraciones. No desplegar sin autorización.

El listado administrativo puede recibir estadísticas calculadas a partir de la misma lectura que sus reportes individuales. Los totales abarcan todos los resultados filtrados, no solo la página visible. El botón de cada comunidad aplica provincia, distrito, corregimiento y comunidad conservando los demás filtros.

Filtros combinables: provincia, distrito, corregimiento, comunidad, fecha inicial/final de recepción (días completos de Panamá), estado operativo, estado de ayuda, seguimiento del caso, tipo de daño, necesidad y archivo activo/archivado/todos. No especificada selecciona registros sin categoría suficiente. El Máster general conserva su alcance completo sin filtros; el Excel por área y el anonimizado utilizan los filtros seleccionados.

Las seis hojas finales son Resumen general, Comunidades, Tipos de daños, Necesidades, Seguimiento y Detalle de reportes. Incluyen tablas nativas con filtros, fechas/números tipados y seis gráficos de barras vinculados a las celdas: seguimiento global, provincias, comunidades, daños, necesidades y seguimiento por comunidad. Con cero resultados no se fabrican datos para llenar los gráficos.

Los informes omiten nombres, teléfonos, coordenadas, Maps, observaciones y descripciones libres por defecto. La opción administrativa Incluir contactos privados conserva las columnas operativas anteriores para gestión autorizada. El anonimizado ignora esa opción y omite también comunidad detallada y texto libre en todas las hojas y metadatos. No exportar fotos ni URLs públicas privadas. Las cadenas de origen nunca se guardan como fórmulas.

### Unidades y significado

- Reportes: números de reporte distintos, sin alterar su consecutivo.
- Grupos familiares declarados: nombre de familia + teléfono + sector coincidentes, con normalización ya existente. Dos reportes de daños distintos del mismo grupo cuentan una vez en ese indicador. Esta agrupación no demuestra identidad familiar única. Los reportes sin identificación familiar se contabilizan aparte.
- Viviendas únicas: no determinadas; no existe identificador estable para contarlas. No equiparar vivienda a reporte, familia o ubicación Maps.
- Pendiente/en seguimiento/con atención registrada: clasificación exclusiva. Atención requiere ayuda parcial/completa con fecha de confirmación. Contactado o visitado sin esa confirmación no implica atención recibida. La ayuda parcial permanece distinguible de la completa.
- Necesidades: únicamente categorías seleccionadas. No inferir desde daños o interpretar texto libre. Las familias pueden figurar en varias necesidades; no sumar esas categorías como familias únicas. Colchones o lugar para dormir se conserva como categoría propia porque no prueba alojamiento temporal. Alojamiento temporal figura No especificada mientras no exista información estructurada inequívoca.

El archivo XLSX está preparado para Excel con componentes OOXML nativos; la apertura física en Microsoft Excel y la activación productiva deben verificarse por separado. No presentar archivos sintéticos de pruebas como datos reales de familias.

## Máster general
Botón "Descargar Máster General": genera un solo archivo .xlsx con todos los reportes guardados, ordenados por provincia, distrito, corregimiento y fecha. Nombre sugerido: REPORTAPA_MASTER_YYYY-MM-DD.xlsx.

## Exportación por área
Botón "Descargar por área": respeta filtros de provincia, distrito, corregimiento y opcionalmente comunidad, estado y necesidad. Nombre de archivo que refleje el filtro y fecha.

## Columnas
ID de reporte, fecha, nombre de persona/familia, teléfono, provincia, distrito, corregimiento, comunidad, enlace Google Maps, descripción de daños, necesidades, detalle de necesidades, estado de seguimiento. Enlaces de fotos solo si se generan URLs seguras con autorización; nunca URLs públicas permanentes para archivos privados.

## Protección
Descargas completas únicamente tras autenticación administrativa. Exportación compartible anonimizada como opción separada, sin nombre, teléfono ni ubicación exacta. Evitar inyección de fórmulas en celdas Excel. Incluir fecha de corte y filtros aplicados.

## Estado
El alcance anterior se conserva como referencia del mecanismo original. La ampliación estadística se desarrolla y prueba en la rama de informes, separada de la rama con despliegue automático.
