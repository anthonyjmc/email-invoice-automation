# 🔁 AI‑Powered Email Invoice Scanner

Automate invoice processing in seconds.  
Upload emails or invoice text — the system extracts key fields and stores them in a secure database.

Built with FastAPI + Supabase + Python + Azure.

**Deployment & operations:** required env vars, limits, scaling, and incident runbook → **[DEPLOYMENT.md](DEPLOYMENT.md)**. **Data protection / retention / logs:** design notes for operators → **[docs/COMPLIANCE.md](docs/COMPLIANCE.md)**.

**Machine API (`GET /invoices`, `POST /process-mock-email`):** use **`Authorization: Bearer …`** or **`X-API-Key`** with secrets stored in **`machine_api_keys`** (SHA-256 hash only; scopes `invoices:read` / `invoices:write` / `invoices:admin`). Legacy **`X-App-Password`** matching **`APP_PASSWORD`** remains if **`API_LEGACY_HEADER_AUTH_ENABLED=true`**. Apply migration **`20260430140000_invoice_idempotency_machine_api_keys.sql`**. **`GET /invoices`** supports **`page`** and **`limit`** (capped by **`INVOICE_LIST_MAX_LIMIT`**). Saves are **idempotent** by **`source_content_hash`** (upload body), **`invoice_ref`** (vendor + invoice # + date), or **`Idempotency-Key`** header on machine POST.

---

## Tests and CI

- **Install dev tools:** `pip install -r requirements.txt -r requirements-dev.txt`
- **Lint:** `ruff check app tests` (rules in `pyproject.toml`: `E`, `F`; `E402` ignored in `app/main.py` for intentional import order after `load_dotenv` / logging setup).
- **Tests:** `pytest` — minimal integration coverage: `/health`, `/metrics` disabled, legacy **login** (success + wrong password), **upload** (happy path `.txt`, bad CSRF, unsupported extension), **`POST /process-mock-email`** with `X-App-Password`, and **parser** on `examples/sample_invoice_email.txt` with Azure skipped (regex fallback). Supabase and Azure are **mocked**; no real keys or network required.
- **CI:** GitHub Actions workflow **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)** runs on every **`push`** and on **`pull_request`** (any branch; there is no `main`/`master`-only filter in `on:`). Steps: install pinned deps, `ruff`, `pytest`. (Rate limits are disabled in tests so login-heavy suites stay stable.)

Runtime dependencies are **version-pinned** in [`requirements.txt`](requirements.txt); [`requirements-dev.txt`](requirements-dev.txt) pins `pytest` and `ruff`.

---

## 🚀 Features

✔ Process invoices from:
- `.txt` files
- `.eml` email exports
- `.msg` Outlook messages

✔ Automatic data extraction:
- Vendor / Company
- Total Amount
- Date
- Currency
- Sender email (coming soon)

✔ Secure login session  
✔ Modern dashboard UI  
✔ Cloud database using Supabase  
✔ Deployable on Render / Azure / AWS

---

## 🧠 How it works

1️⃣ Upload an invoice email via dashboard

2️⃣ Azure OpenAI structured-output agent extracts key fields

3️⃣ Regex fallback is applied if the AI misses anything

4️⃣ Data is stored and visible in the dashboard

5️⃣ Exportable for accounting (coming soon)

---

## 🛠 Tech Stack

| Layer | Technology |
|------|------------|
| Backend API | FastAPI |
| Frontend | Jinja2 HTML templates |
| Parsing | Azure OpenAI (GPT-4o / GPT-4o-mini) + Regex + MIME parsing |
| Auth | Secure cookie sessions |
| Database | Supabase PostgreSQL |
| Deployment | Render / Azure App Service |
| Agent | Azure OpenAI Structured Output Agent |

---

## 📸 Screenshots

<img width="1366" height="635" alt="Screenshot (84)" src="https://github.com/user-attachments/assets/dc0f3ea8-f202-4df0-9c71-494005480dd4" />
<img width="1366" height="638" alt="Screenshot (86)" src="https://github.com/user-attachments/assets/70247ae0-c0bc-421e-9ff6-156c9f715c9f" />
<img width="1366" height="633" alt="Screenshot (87)" src="https://github.com/user-attachments/assets/5c639683-a592-426d-8d25-28b3a446aa34" />

---

## 🧪 Local Development

### Requirements
- Python 3.10+
- Supabase project (with URL + key)
- Azure OpenAI deployment
- Recommended: Virtual environment

git clone https://github.com/anthonyjmc/email-invoice-automation.git
cd email-invoice-automation

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

Create env file:
cp .env.example .env  # Windows PowerShell: Copy-Item .env.example .env

Update `.env` with your real Supabase and Azure OpenAI credentials before starting the server. Set `SESSION_SECRET` to a long random string (at least 32 characters), unique per environment—for example `openssl rand -hex 32`.

**Auth:** `WEB_AUTH_PROVIDER=legacy` uses a shared `AUTH_PASSWORD` (good for demos). For production, use `WEB_AUTH_PROVIDER=supabase` and create users under **Supabase → Authentication**; then sign in with email and password. Set `SESSION_COOKIE_SECURE=true` when serving the app over HTTPS.

**Uploads:** Max size is controlled with `MAX_UPLOAD_FILE_BYTES` (default 10 MB). The server checks **content signatures** (not only the file extension), rejects unsafe names, writes uploads under a **random temp filename**, and deletes the temp file after processing. Optional **ClamAV** (or any CLI): set `UPLOAD_AV_SCAN_ENABLED=true`, `UPLOAD_AV_SCAN_COMMAND` with a `{path}` placeholder (e.g. `clamscan --no-summary {path}`), and `UPLOAD_AV_SCAN_PDF_ONLY=true` to scan PDFs only.

### Docker (optional)

For a reproducible runtime (K8s, ACI, or local parity), use the root **[`Dockerfile`](Dockerfile)** and **[`docker-compose.yml`](docker-compose.yml)**. Details, ClamAV build-arg, and Redis profile → **[DEPLOYMENT.md](DEPLOYMENT.md)** (section *Docker and Compose*).

### Rate limiting (multi-instance)

- **Default:** in-memory counters (one per process; fine for a single worker).
- **Production:** set **`REDIS_URL`** (e.g. `redis://:password@host:6379/0`) so login and upload limits are shared across **all workers/replicas**. Keys use the prefix **`RATE_LIMIT_REDIS_KEY_PREFIX`** (default `rl:v1`).
- **Behind a proxy:** set **`RATE_LIMIT_TRUST_X_FORWARDED_FOR=true`** only if you trust the proxy to set `X-Forwarded-For` correctly.
- **Edge:** prefer additional limits at **Cloudflare**, API Gateway, or your load balancer so abuse never reaches the app.

### Observability (logs, correlation IDs, metrics, alerts)

- **Structured logs:** Set **`LOG_FORMAT=json`** so each line is one JSON object (easy to ship to Datadog, CloudWatch Logs, Grafana Loki, ELK). Use **`LOG_LEVEL`** (`INFO`, `DEBUG`, …). With JSON logs, prefer **`uvicorn app.main:app --no-access-log`** to avoid duplicate unstructured access lines (the app emits **`http_request`** with `method`, `path`, `route`, `status_code`, `duration_ms`, **`correlation_id`**).
- **Correlation IDs:** Every request gets an **`X-Request-ID`** (reuses incoming **`X-Request-ID`** or **`X-Correlation-ID`** when present). The same value appears in access logs and in **`GET /health`** as `correlation_id` when available—use it to tie browser → proxy → app → DB logs during an incident.
- **Metrics:** Enable **`OBSERVABILITY_METRICS_ENABLED=true`** to expose **`GET /metrics`** in Prometheus format: **`http_server_requests_total`** (labels `method`, `route`, **`status_class`** e.g. `5xx`) and **`http_server_request_duration_seconds`** histogram. Set **`METRICS_BEARER_TOKEN`** for in-app Bearer auth in addition to network isolation (private scrape, allowlist, mTLS at the proxy). Do not expose **`/metrics`** on the public internet without layered controls.
- **Queues:** This service does not run a job queue. If you add **Celery / RQ / Dramatiq**, export queue depth and worker failures as separate metrics and scrape workers, not only the API process.
- **Health for alerting:** **`GET /health`** returns **`status: degraded`** when **`REDIS_URL`** is set but Redis is down or unreachable (`redis: error`), so uptime checks can page before rate limits silently fall back to per-process memory.
- **Alert ideas (Prometheus / Alertmanager):** alert on **`rate(http_server_requests_total{status_class="5xx"}[5m]) > 0`** (or a threshold), high **`histogram_quantile(0.99, …http_server_request_duration_seconds…)`**, **`health` JSON `status != ok`** from a blackbox or synthetic check, and sustained **`rate_limit_redis_fallback`** log volume (Redis instability).

### HTTPS and security headers

- **TLS:** Terminate HTTPS at your **reverse proxy** (nginx, Caddy, Traefik, cloud load balancer) and forward HTTP to Uvicorn on a private network, or use TLS passthrough.
- **Headers:** The app can send **`X-Content-Type-Options: nosniff`**, **`X-Frame-Options`**, **`Referrer-Policy`**, **`Permissions-Policy`**, **`Content-Security-Policy`** (default allows inline `script`/`style` for Jinja pages; **`SECURITY_CSP_USE_NONCES=true`** tightens **`script-src`** with per-request nonces when **`SECURITY_CSP`** is unset; **`style-src`** keeps **`'unsafe-inline'`** until styles are refactored), optional **`Cross-Origin-Opener-Policy`**, and **`Strict-Transport-Security` (HSTS)** when **`SECURITY_ENABLE_HSTS=true`** (only after you are sure every user hits HTTPS; use long **`SECURITY_HSTS_MAX_AGE`** and optionally **`SECURITY_HSTS_PRELOAD`** if you submit to the preload list).
- **Disable:** set **`SECURITY_HEADERS_ENABLED=false`** if your edge already injects the same headers and you want to avoid duplicates.

### Supabase in production (RLS, keys, migrations, backups)

- **Migrations:** SQL lives under `supabase/migrations/`. Apply with the [Supabase CLI](https://supabase.com/docs/guides/cli) (`supabase link` then `supabase db push`) or by running the SQL in the Supabase SQL Editor. The included migration creates `public.invoices`, adds `user_id` → `auth.users`, enables **RLS**, and adds policies so **`authenticated`** users can only **select/insert/update/delete their own rows** (`user_id = auth.uid()`).
- **Anon vs service role:** The **anon** key is safe to ship to clients only if you also rely on strict RLS and pass the user JWT (this app never sends the anon key to the browser for DB calls). The **service role** key **bypasses RLS** and must exist **only on the server** (e.g. `SUPABASE_SERVICE_ROLE_KEY` in Render). With **`WEB_AUTH_PROVIDER=supabase`**, the API uses the user session JWT so RLS applies per user. With **`WEB_AUTH_PROVIDER=legacy`** and RLS enabled, set **`SUPABASE_SERVICE_ROLE_KEY`** on the server so dashboard/API writes still work; machine routes (`/invoices`, `/process-mock-email`) already prefer the service role when it is set.
- **Backups:** On hosted Supabase, use project **Backups** (paid tiers include PITR). Export critical tables periodically if you need an extra copy outside Supabase.
- **Hardening:** Rotate keys on incident, restrict Dashboard access, review **Auth** providers and **Database** logs, and add more policies (e.g. separate roles) as the product grows.

Run Locally:
uvicorn app.main:app --reload

Production-style logging (JSON + single access log from the app):

```bash
LOG_FORMAT=json uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Then open:
👉 http://127.0.0.1:8000

---

If you want to automate business workflows or email processing:
📩 anthony.marquez@upr.edu

⭐ If this project helped you, please star the repo!

👤 Anthony J. Marquez Camacho
Computer Engineer — AI & Automation Developer
