# Deployment & operations

This document covers **required environment variables**, **limits**, **how to scale**, and an **incident runbook**. Authoritative defaults live in `app/config.py`; hard-coded rate limits are in `app/main.py`.

---

## Required environment variables

The app fails at startup if any of these are missing or invalid (Pydantic `Settings`).

| Variable | Notes |
|----------|--------|
| `SESSION_SECRET` | At least **32** characters. Unique per environment. Example: `openssl rand -hex 32`. |
| `APP_PASSWORD` | Used by **`verify_password`** on machine routes (`GET /invoices`, `POST /process-mock-email`) via header `X-App-Password`. |
| `SUPABASE_URL` | Project URL, e.g. `https://<ref>.supabase.co`. |
| `SUPABASE_ANON_KEY` | Supabase anon (publishable) key; server uses it with RLS-aware clients where applicable. |
| `AUTH_PASSWORD` | **Legacy** login shared password when `WEB_AUTH_PROVIDER=legacy`. Still required at startup even if you use Supabase Auth (set a strong unused value if only Supabase is used, or align with your policy). |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint URL. |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key. |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (model deployment in Azure). |

Copy from [`.env.example`](.env.example) and fill real values. **`render.yaml`** lists only a subset of keys; add the rest in the host’s environment UI (Render **Environment**, Azure **Configuration**, etc.).

---

## Strongly recommended for production

| Variable | Purpose |
|----------|---------|
| `WEB_AUTH_PROVIDER=supabase` | Per-user Supabase Auth instead of a shared `AUTH_PASSWORD`. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only. Needed for **legacy + RLS**, or for **`/invoices`** / **`/process-mock-email`** when you rely on service role; never expose to browsers. |
| `SESSION_COOKIE_SECURE=true` | When the app is only served over **HTTPS**. |
| `REDIS_URL` | Shared **rate limits** across multiple workers/replicas. |
| `LOG_FORMAT=json` | Structured logs for aggregators (see README observability section). |
| `SECURITY_ENABLE_HSTS=true` | Only when **all** traffic is HTTPS behind a correct TLS setup. |

Never set `APP_DEBUG=true` in production (it exposes validation details in 422 responses).

---

## Optional variables & operational tuning

| Area | Variables (defaults in `config.py`) |
|------|--------------------------------------|
| Session | `SESSION_MAX_AGE_SECONDS` (8h), `SESSION_COOKIE_SAMESITE` (`lax` / `strict` / `none`) |
| Uploads | `MAX_UPLOAD_FILE_BYTES` (10 MiB), `UPLOAD_AV_SCAN_*` (optional AV CLI on PDF by default) |
| Rate limit / Redis | `RATE_LIMIT_REDIS_KEY_PREFIX`, `RATE_LIMIT_TRUST_X_FORWARDED_FOR` (only behind a **trusted** proxy) |
| Security headers | `SECURITY_HEADERS_ENABLED`, `SECURITY_CSP`, HSTS-related keys, `SECURITY_CROSS_ORIGIN_OPENER_POLICY` (empty to omit COOP) |
| Observability | `LOG_LEVEL`, `OBSERVABILITY_METRICS_ENABLED`, `OBSERVABILITY_ACCESS_LOG` |
| Debug | `APP_DEBUG` (default `false`) |

---

## Fixed limits (code)

These are **not** environment-driven today; changing them requires editing `app/main.py` (or refactoring to settings).

| Limit | Value | Scope |
|-------|--------|--------|
| Login rate limit | **5** requests per **60** seconds | Per client IP (and action `login`) |
| Upload rate limit | **10** requests per **300** seconds (5 min) | Per client IP (action `upload_invoice`) |
| Max upload size | Default **10 MiB** | `MAX_UPLOAD_FILE_BYTES` |

Rate limiting uses **Redis** when `REDIS_URL` is set; otherwise **in-memory** (per process only—see scaling below).

---

## How to scale

### Horizontal (more traffic / HA)

1. **Run multiple Uvicorn workers or replicas** (e.g. `gunicorn` with `uvicorn.workers.UvicornWorker`, Kubernetes replicas, Render **multiple instances** on paid tiers).
2. Set **`REDIS_URL`** so login and upload counters are **shared** across all processes. Without Redis, each worker has its own counters and abuse limits are weaker.
3. Put **`RATE_LIMIT_TRUST_X_FORWARDED_FOR=true`** only if the edge sets **`X-Forwarded-For`** correctly and you trust it; otherwise rate limits key off the proxy IP.
4. **Supabase** scales on the database side; watch connection usage and [Supabase pooler](https://supabase.com/docs/guides/database/connecting-to-postgres) if you open many concurrent connections from many workers.
5. **Azure OpenAI**: watch **TPM/RPM quotas** and latency; scale deployment SKU or add regional endpoints as needed.

### Vertical

Increase CPU/RAM for the web process if parsing large PDFs or AV scanning is heavy; keep **`UPLOAD_AV_SCAN_TIMEOUT_SECONDS`** aligned with worst-case scan time.

### Edge / safety

Use a **CDN or WAF** (Cloudflare, API Gateway) for DDoS and coarse rate limits in front of the app.

### Metrics & health

- **`GET /health`**: synthetic checks; expect **`status: degraded`** if Redis is configured but **`redis`** is not `ok`.
- **`GET /metrics`**: Prometheus scrape when **`OBSERVABILITY_METRICS_ENABLED=true`**; do not expose publicly without protection.

---

## Render (reference)

[`render.yaml`](render.yaml) defines a sample web service. You must still configure **all required variables** in the Render dashboard (including **Azure** and **`AUTH_PASSWORD`** if applicable). Typical start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

For JSON logs without duplicate Uvicorn access lines:

```bash
LOG_FORMAT=json uvicorn app.main:app --host 0.0.0.0 --port 10000 --no-access-log
```

---

## Incident runbook

Use **correlation IDs**: responses and logs may include **`X-Request-ID`** / **`request_id`** / `correlation_id` in **`GET /health`**. Search logs for that id across **proxy → app → Supabase / Azure**.

### 1. Users cannot log in

| Check | Action |
|-------|--------|
| Wrong provider | Confirm `WEB_AUTH_PROVIDER` (`legacy` vs `supabase`). |
| Legacy | Verify `AUTH_PASSWORD`; rate limit message → wait or inspect Redis keys `rl:v1:login:*`. |
| Supabase | Supabase Auth status, user exists, lockout; app logs for `sign_in` / HTTP errors. |
| Cookies | HTTPS + `SESSION_COOKIE_SECURE=true`; SameSite compatible with your domain. |

### 2. Uploads fail or “rate limited”

| Check | Action |
|-------|--------|
| Size / type | `MAX_UPLOAD_FILE_BYTES`; file must match sniffed kind (see upload security). |
| Rate limit | Redis vs memory; increase workers only with Redis for fair limits. |
| AV | Logs for `av_*` errors; `UPLOAD_AV_SCAN_COMMAND` and timeouts. |

### 3. Dashboard empty or save errors

| Check | Action |
|-------|--------|
| Supabase | Project paused, RLS policies, JWT vs service role (`SUPABASE_SERVICE_ROLE_KEY` for legacy+RLS). |
| Logs | `save_failed`, `parse_failed` flows; `unhandled_exception` with stack (server only). |

### 4. `/health` degraded

| Check | Action |
|-------|--------|
| `redis: error` | Redis reachability, auth string in `REDIS_URL`, network/firewall. |
| Fallback | Logs for **`rate_limit_redis_fallback`** → Redis errors; app still runs with per-process limits. |

### 5. High 5xx or timeouts

| Check | Action |
|-------|--------|
| App logs | `http_request` with `status_code`, `duration_ms`; `unhandled_exception`. |
| Azure OpenAI | Quota, 429, deployment name; regional latency. |
| Supabase | Timeouts, pool size, incident page. |

### 6. Suspected compromise or secret leak

1. Rotate **`SESSION_SECRET`** (invalidates sessions).
2. Rotate **Supabase** keys, **Azure** key, **`APP_PASSWORD`**, **`AUTH_PASSWORD`** as applicable.
3. Review Supabase **Auth** and **Database** logs; enable audit if available.

### 7. Rollback

1. Redeploy previous **image/commit** on your platform.
2. If a bad migration was applied, restore DB from **backup** (Supabase backups / PITR) per your DR plan—test restores regularly.

### Escalation

- **Supabase**: status page + support per plan.  
- **Azure**: portal metrics + support ticket for quota or platform issues.  
- **Render / other PaaS**: platform status and support.

---

## Related docs

- [README.md](README.md) — local setup, rate limiting, observability, HTTPS, Supabase RLS.
