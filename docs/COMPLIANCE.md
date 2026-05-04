# Cumplimiento, datos personales y operación segura

Este documento describe **decisiones de diseño** y **recomendaciones operativas** para quien despliega la aplicación (RGPD / GDPR y prácticas afines). No sustituye asesoramiento legal.

## Rol del software

La demo procesa **facturas y correos** que pueden contener datos personales (nombre, dirección, importes, líneas de detalle, metadatos de remitente). El **responsable del tratamiento** es quien opera el despliegue y define finalidades y bases jurídicas.

## Retención y minimización

- **Almacenamiento:** Los campos persistidos dependen del esquema Supabase y de lo que extraigan los parsers (PDF, EML, MSG, etc.). Revise qué columnas almacena su proyecto y elimine o anonimice lo que no necesite.
- **Retención:** La aplicación **no impone** plazos de borrado automático. Debe definir políticas en base de datos (jobs de purga, particionado por fecha) o en procesos externos alineados con su política de retención.
- **Minimización:** Evite guardar cuerpos de correo completos o adjuntos si solo necesita campos estructurados de factura; use hashes (p. ej. deduplicación) en lugar de duplicar contenido cuando baste.

## Derecho de supresión y portabilidad

- **Supabase:** Los borrados y exportaciones (DSR) se implementan típicamente con políticas RLS, APIs administrativas o scripts contra las tablas de facturas. Este repositorio no incluye un flujo de “olvido” de usuario final; debe añadirlo según su modelo (usuario = `user_id` en filas cuando `WEB_AUTH_PROVIDER=supabase`).
- **Claves y sesiones:** Revocar sesión no borra facturas; el borrado de datos es una operación explícita sobre el almacén.

## Logs y PII

- **Logs de acceso** (`OBSERVABILITY_ACCESS_LOG`): Incluyen método, ruta, código de estado, duración y `correlation_id`. **No** incluyen cuerpos de petición por defecto; evite registrar payloads de subida o respuestas con datos de factura en nivel `DEBUG`.
- **Errores:** Las trazas pueden contener fragmentos de contexto; configure niveles de log y agregadores para **filtrar o enmascarar** campos sensibles.
- **Métricas Prometheus:** Las etiquetas usan método, plantilla de ruta y clase de estado; **no** deben incluir direcciones de correo ni totales de factura. Si amplía métricas, no etiquete series con PII.

## `/metrics` y superficie de ataque

- Con `OBSERVABILITY_METRICS_ENABLED=true`, el endpoint debe estar **solo en red privada** o detrás de política de red (allowlist, mTLS en el proxy).
- Opcionalmente, `METRICS_BEARER_TOKEN` exige `Authorization: Bearer …` en la aplicación; no reemplaza el aislamiento de red pero reduce el riesgo de exposición accidental.

## CSP y plantillas

- Con `SECURITY_CSP_USE_NONCES=true` (y sin `SECURITY_CSP` personalizada), `script-src` usa un **nonce por petición**; las plantillas HTML deben alinear el `<script>` con ese nonce. `style-src` sigue permitiendo `'unsafe-inline'` por compatibilidad con CSS embebido en Jinja; puede endurecerse con hashes o nonces si refactoriza estilos.

## Subprocesadores

- **Supabase** (base de datos, Auth, almacenamiento según configuración).
- **Azure OpenAI** (si está habilitado para extracción): el operador debe revisar contratos de tratamiento de datos y regiones.

## Documentación relacionada

- `DEPLOYMENT.md` — cabeceras, métricas, HSTS.
- `README.md` — observabilidad y seguridad en alto nivel.
