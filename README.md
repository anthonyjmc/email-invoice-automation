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
