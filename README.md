# 💰 WealthOS — Personal Finance & Net Worth Tracker

A fully local, full-stack personal finance tracker built with **FastAPI + SQLite** (backend) and **React + Tailwind CSS** (frontend). Zero cloud dependency — all data stays on your machine.

---

## ✨ Features

### 📊 Dashboard
- Net worth = Investments + Bank Balances − Credit Card Dues
- Area chart of net worth over time
- Portfolio allocation donut chart
- Monthly spending gauge vs salary
- Live alerts for overspending & high utilization

### 💼 Investment Portfolio (9 Asset Classes)
| Asset Class | Platform |
|---|---|
| Indian Stocks | Groww |
| Mutual Funds | Groww |
| US Stocks | INDMoney |
| Crypto | CoinSwitch |
| Gold ETF | Groww |
| Silver ETF | Groww |
| Sovereign Gold Bond | Groww |
| Digital Gold | AuraGold |
| Digital Silver | AuraGold |

- Track current value, invested amount, P&L, allocation %
- CSV import for all broker export formats
- Manual entry & edit for every data point

### 💳 Credit Cards (4 Configured)
- CSB, Swiggy HDFC, Axis Neo, Axis MyZone
- Statement cycle, credit limit, utilization bar
- Per-card transaction entry with category tagging
- CSV statement import
- **Alerts:** 40% salary threshold, 80% utilization warning

### 🏦 Bank Accounts (3 Configured)
- Jupiter (Main), Equitas (Dormant), DBS (Emergency)
- Balance, monthly inflow/outflow tracking
- Emergency fund coverage indicator (3-6 month target)

### 🤖 AI Insights Engine (Rule-Based)
- Savings rate recommendation (30–40% target)
- SIP allocation breakdown: ₹25,000/month across 7 categories
- Portfolio allocation vs recommended (60/20/10/10)
- Credit behaviour flags & budget limits
- 80C tax planning tracker
- Wealth milestone projections (₹10L → ₹1Cr)
- Financial health score (A–D grade)

### 📄 Statement Import
- PDF import for HDFC / Axis / CSB credit cards and DBS / Federal (Jupiter) / Equitas / Canara bank statements
- **Password-protected PDFs and XLSX**: the app prompts for the password on upload — no need to unlock files first
- **Evidence-based format detection**: the detected parser is trusted only if it actually finds transactions; otherwise all parsers compete and a generic text-line parser is the final fallback, so unknown bank formats still import
- **Learned categories**: when transactions can't be categorized, a popup asks you once — the merchant→category rule is remembered, applied to past transactions, and used in every future import (learned rules always beat keyword guesses)

### ⚙️ Additional
- PIN-based local authentication — **all data endpoints require the session token**
- Monthly auto-snapshots (1st of every month)
- Excel export (investments, cards, accounts, history)
- One-click SQLite database backup
- Dark mode (default)

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+**
- **Node.js 18+**

### One-command setup:
```bash
chmod +x setup.sh
./setup.sh
```

Then open **http://localhost:3000** in your browser.

> On first launch, you'll be asked to set a 4–6 digit PIN.

### 📱 Use from your phone

```bash
./start.sh
```

This builds the frontend and serves **everything from one port** — the script
prints your machine's address (e.g. `http://192.168.1.5:8000`). Open it on
your phone's browser (same Wi-Fi) and add it to your home screen.

To use it away from home, install [Tailscale](https://tailscale.com) (free)
on this machine and your phone — then the same URL works from anywhere over a
private encrypted network, with nothing exposed to the internet.

Login is rate-limited (5 wrong PINs → 5-minute lockout) and every data
endpoint requires the session token, so LAN/Tailscale exposure is safe.
Do **not** port-forward this to the public internet.

---

## 🗂️ Project Structure

```
finance-tracker/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLite + SQLAlchemy setup
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   ├── requirements.txt
│   └── routers/
│       ├── auth.py          # PIN auth + JWT
│       ├── investments.py   # Portfolio CRUD + CSV import
│       ├── credit_cards.py  # Card CRUD + transaction tracking
│       ├── bank_accounts.py # Bank account management
│       ├── dashboard.py     # Aggregation + net worth history
│       ├── suggestions.py   # AI insights engine
│       └── export.py        # Excel + DB backup export
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx         # PIN keypad login
│   │   │   ├── Dashboard.jsx     # Main overview
│   │   │   ├── Investments.jsx   # Portfolio management
│   │   │   ├── CreditCards.jsx   # Card tracking
│   │   │   ├── BankAccounts.jsx  # Bank management
│   │   │   └── Suggestions.jsx   # AI insights
│   │   ├── components/
│   │   │   └── Layout.jsx        # Sidebar navigation
│   │   └── api/
│   │       └── client.js         # Axios API client
│   └── ...config files
├── setup.sh             # One-click install & launch
└── README.md
```

---

## 🔒 Security & Privacy

- All data stored in **SQLite at `backend/finance_tracker.db`**
- No telemetry; the only external calls are optional Yahoo Finance price refreshes
- Signed session token (30-day expiry) stored in `localStorage`; every data API requires it
- To change PIN: Settings → Change PIN (or call `POST /api/auth/change-pin`)
- Forgot your PIN? Clear it locally: `sqlite3 backend/finance_tracker.db "DELETE FROM users;"` then set a new one

---

## 📤 CSV Import Formats

### Groww Stocks / MF Export
Columns: `Stock`, `Invested Amount`, `Current Value`, `Units`

### INDMoney US Stocks
Columns: `Name`, `Buy Value`, `Present Value`, `Quantity`

### CoinSwitch Crypto
Columns: `Symbol`, `Invested Amount`, `Current Amount`, `Qty`

---

## 🛠️ Manual Start (if setup.sh fails)

**Backend:**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 💡 Salary Context Used

| | |
|---|---|
| **Current Salary** | ₹5.15 LPA (₹38,000/month) |
| **New CTC** | ₹13,95,565 |
| **Fixed CTC** | ₹12,45,565 |
| **Monthly Gross** | ₹1,00,000 |
| **Performance Bonus** | ₹1,00,000 (July, pro-rata) |
| **Non-Cash Benefits** | ₹50,000 (Insurance + Advantage Club) |

All suggestions, SIP allocations, and alerts are calibrated to the **new salary**.

---

## 📅 Roadmap / Future
- [ ] Groww/INDMoney official API integration (when available)
- [ ] SMS parser for auto-categorization
- [ ] Recurring expense tracker
- [ ] Tax P&L report (STCG/LTCG calculator)
- [ ] Multi-device sync (optional, opt-in)
