# 🔁 AI‑Powered Email Invoice Scanner

Automate invoice processing in seconds.  
Upload emails or invoice text — the system extracts key fields and stores them in a secure database.

Built with FastAPI + Supabase + Python + Azure.

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

Run Locally:
uvicorn app.main:app --reload

Then open:
👉 http://127.0.0.1:8000

---

If you want to automate business workflows or email processing:
📩 anthony.marquez@upr.edu

⭐ If this project helped you, please star the repo!

👤 Anthony J. Marquez Camacho
Computer Engineer — AI & Automation Developer
