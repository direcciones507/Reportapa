# Número de cédula del responsable

Campo opcional `reports.data.cedula`, privado y asociado al mismo reporte familiar.
Se normaliza a mayúsculas y se valida como tres grupos separados por guiones;
primer grupo alfanumérico (1–6), segundo y tercero numéricos (1–6 cada uno).
La validación es de formato, no verifica identidad ante ninguna entidad.

Migración 008: restricción CHECK idempotente sobre el JSONB existente, sin
UPDATE, valores inventados, índice único ni cambios en las claves de duplicados.
Se aplica en la transacción de arranque con el bloqueo de migraciones existente.
Los registros históricos sin el campo permanecen intactos; UI/PDF muestran
«Sin informar» y Excel deja la celda vacía.

Formulario: junto al nombre en escritorio; debajo del nombre en pantalla estrecha.
Panel privado y ficha PDF: muestran el campo con los controles de acceso existentes.
Excel maestro/área: incluye columna al final solo con `include_personal=true`.
Exportación anónima y resúmenes: excluyen el campo y el valor, incluso si se pide
`include_personal=true`. La respuesta pública de registro conserva solo la
confirmación existente y nunca devuelve la cédula.

La integración MCP puede recibir el campo opcional. No cambia consentimiento,
OAuth, seguimiento ni entrega de ayuda. No se agrega la cédula a WhatsApp.

Pruebas: formatos válidos/inválidos, omisión compatible con idempotencia anterior,
claves de duplicados idénticas, PDF de una página, Excel privado/anonimizado,
migración repetible sin alterar filas históricas y recorrido PostgreSQL→consulta
administrativa→PDF→Excel en PostgreSQL desechable de CI.
