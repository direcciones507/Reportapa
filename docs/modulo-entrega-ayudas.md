# ReportaPA | Módulo de entrega de ayudas

Estado: desarrollo aislado. No desplegar ni alterar el formulario actual.

## Rutas
- Entrada pública: dos opciones, «Reportar daños» (conserva el enlace y formulario actual) y «Entrega de ayuda».
- Entrega de ayuda: autenticación con identificador individual y código secreto, validados por el servidor.
- Formulario autenticado: nombre completo del beneficiario, cédula, lugar y tipo de ayuda entregada. Fecha, hora e identidad del responsable se asignan en servidor.
- ADMIN existente: nueva sección «Entrega de ayudas» con «Personal autorizado» y «Registros de entrega».

## Reglas de implementación
1. Localizar primero el código que realmente sirve reportapa.online y su backend. Este repositorio puede contener documentación distinta de la aplicación desplegada. No crear una aplicación paralela.
2. Mantener intactos los reportes de daños, formularios, URLs, registros históricos y exportaciones existentes.
3. ADMIN crea y revoca credenciales por persona. Generar códigos aleatorios únicos, mostrar solo al emitir, almacenar hash seguro; nunca guardar códigos en Git ni en texto plano.
4. Limitar intentos de acceso, sesiones con expiración, autorización por rol en servidor y protección contra CSRF cuando corresponda.
5. El responsable autenticado no debe poder consultar listados de familias ni datos de otras entregas; únicamente registrar entregas y recibir confirmación.
6. Almacenar cédulas y nombres de beneficiarios en base privada, con acceso restringido y bitácora de acciones administrativas.
7. Proteger envíos contra duplicados por reintento mediante clave de idempotencia; marcar coincidencias de cédula para revisión, sin bloquear automáticamente ayudas legítimas.
8. Permitir exportación de entregas solo desde ADMIN autenticado.
9. Preparar migraciones reversibles y pruebas aisladas antes de desplegar; no activar producción sin autorización.

## Criterios de aceptación
- El reporte público existente continúa sin cambios.
- Una credencial revocada no puede iniciar sesión ni registrar entregas.
- Una persona no autorizada no puede consultar ni crear entregas.
- Cada entrega registra beneficiario, cédula, lugar, tipo, responsable y fecha/hora.
- ADMIN puede agregar, suspender y consultar responsables, así como filtrar entregas.
- Un reenvío accidental no duplica una entrega.
