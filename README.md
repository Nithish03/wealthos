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

### ⚙️ Additional
- PIN-based local authentication
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
- No network calls, no telemetry, no external APIs
- JWT token (30-day expiry) stored in `localStorage`
- To change PIN: Settings → Change PIN (or call `POST /auth/change-pin`)

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
