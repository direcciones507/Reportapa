# Conservación, eliminación y recuperación de ReportaPA

## Datos y conservación

Los nuevos reportes guardan nombre completo del responsable, nombre de familia y total de afectados. La composición opcional registra solo cantidades en grupos no superpuestos (0-5, 6-17, 18-59, 60 o más) y personas con discapacidad, ya incluidas en el total. No solicitar diagnósticos ni nombres de miembros. Los registros antiguos conservan sus datos originales; no se inventan responsables diferentes, familias ni cantidades.

Los reportes activos se conservan para su seguimiento. Archivar es una acción reversible, no un borrado: mantiene datos, historial y fotos y los separa de la vista activa. El Máster General incluye activos y archivados; las exportaciones por área y anonimizadas respetan el filtro de archivo. No hay purgas automáticas de familias o reportes. Revisar periódicamente la necesidad de conservación y eliminar expresamente los casos que el propietario determine; no se fija ni promete un plazo legal.

## Eliminación definitiva privada

Solo el propietario autenticado puede eliminar por la ruta privada existente de reportes, con CSRF y confirmación exacta `ELIMINAR RPA-…`. La operación borra el registro completo (datos personales, ubicación, cantidades, fotos asociadas e historial de ayuda) de PostgreSQL. Los datos no se copian a otra tabla de reportes. Después se eliminan los archivos privados.

Para tolerar un cierre abrupto o fallo del volumen entre el commit SQL y el borrado físico, una cola operativa en la misma base conserva únicamente los nombres opacos de archivos pendientes. Ninguna ruta privada o pública permite ver una foto cuyo reporte ya fue eliminado. La limpieza se reintenta al arrancar y cada 30 segundos; un fallo devuelve 202 y un aviso de fotos pendientes, nunca afirma falsamente que se borró el archivo. La cola desaparece al completar la limpieza. La confirmación protege contra errores, pero no convierte la eliminación en reversible.

Se conserva un registro mínimo de eliminaciones: ID opaco del reporte y fecha, sin nombre, teléfono, familia, composición, ubicación, observaciones ni imágenes. Sirve exclusivamente para impedir que un respaldo anterior reintroduzca casos eliminados. Se descarga desde el panel como `REPORTAPA_ELIMINACIONES.json`, con sesión autorizada. Guardar la copia más reciente en almacenamiento privado del propietario después de eliminaciones y antes de una restauración.

## Tratamiento de respaldos

Eliminar del sistema activo no modifica snapshots ni Excel/PDF previamente descargados. Las copias anteriores de datos privados deben quedar restringidas y desaparecer conforme vence la política de respaldos que se configure antes de producción. El propietario debe aprobar frecuencia y retención; sin esa configuración no se afirma que exista respaldo ni un plazo garantizado para desaparición de copias. No contratar ni habilitar backups sin autorización.

Propuesta operativa para aprobar: conservar únicamente las copias necesarias para recuperación con una ventana máxima de 30 días, ajustada a los calendarios disponibles del proveedor, y retirar exports privados que hayan dejado de ser necesarios. No se implementa ni ejecuta esa propuesta automáticamente. Mantener el registro mínimo de eliminaciones mientras existan copias restaurables que puedan contener esos IDs. Después revisar su necesidad; no contiene el contenido del reporte.

## Recuperación coherente

1. Mantener `PUBLIC_REPORTS_ENABLED=false` y limitar el acceso administrativo mientras se recupera. Descargar y conservar fuera del snapshot el registro de eliminaciones más reciente **antes** de restaurar.
2. Recuperar PostgreSQL y el volumen privado de fotos con fechas de corte compatibles. Verificar conteos de reportes, nombres de fotos referenciados y existencia/lectura de los archivos. Las sesiones recuperadas deben invalidarse antes de entregar acceso; usar una nueva contraseña privada y eliminar sesiones antiguas en la operación autorizada.
3. Comparar los IDs restaurados contra el registro reciente de eliminaciones. Reaplicar los borrados desde el mismo panel/API privada, con confirmación exacta por reporte, antes de volver a habilitar acceso o recepción. Las fotos de esos casos deben desaparecer también. No se crea otro sistema de recuperación.
4. Si se pierde el registro de eliminaciones o no coinciden los conjuntos de fotos/base, no abrir recepción ni afirmar que la restauración es coherente; resolver la discrepancia con el propietario.
5. Verificar login, fotos privadas, historial, Excel y PDF, y autorizar separadamente la reapertura. Las restauraciones nativas de Railway permanecen limitadas al mismo proyecto/entorno; para un ensayo aislado usar copias lógicas y fotos de prueba.

## Qué se ha probado y qué falta

Pruebas automatizadas con base y fotos descartables comprueban archivo/restauración del archivo sin pérdida de datos, eliminación completa, falta de autorización/CSRF/confirmación, fallo de unlink con reintento, reinicio sobre el mismo directorio persistente de prueba y recuperación de copia seguida de reaplicación del registro de eliminaciones. No se han creado snapshots ni restaurado volúmenes Railway reales. Sigue pendiente un ensayo autorizado de persistencia y recuperación en infraestructura exclusiva de ReportaPA, además de las pruebas físicas Android/iPhone/tablet.
