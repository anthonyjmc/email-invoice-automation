# 🔁 AI-Powered Email Invoice Automation

Automate invoice processing in seconds.  
Upload emails or invoice text — the system extracts key fields and stores them in a secure database.

Built with FastAPI + Supabase + Python.

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
2️⃣ AI-assisted parser extracts key invoice fields  
3️⃣ Data is stored and visible in the dashboard  
4️⃣ Exportable for accounting (coming soon)

---

## 🛠 Tech Stack

| Layer | Technology |
|------|------------|
| Backend API | FastAPI |
| Frontend | Jinja2 HTML templates |
| Parsing | Regex + Email MIME parsing |
| Auth | Secure cookie sessions |
| Database | Supabase PostgreSQL |
| Deployment | Render (free tier compatible) |

---

## 📸 Screenshots

> Coming soon: Dashboard + Upload UI 🚀

---

## 🧪 Local Development

### Requirements
- Python 3.10+
- Supabase project (env variables set)
- Recommended: Virtual environment

```bash
git clone https://github.com/anthonyjmc/email-invoice-automation.git
cd email-invoice-automation

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

Run Locally:
uvicorn app.main:app --reload

Then open:
👉 http://127.0.0.1:8000

👤 Anthony J. Marquez Camacho
Computer Engineer — AI & Automation Developer

If you want to automate business workflows or email processing:
📩 anthonyjmarquez@upr.edu

⭐ If this project helped you, please star the repo!