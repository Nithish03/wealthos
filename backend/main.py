from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base
import models

# Create all tables first
Base.metadata.create_all(bind=engine)

# Import routers (BankTransaction table is created inside bank_accounts router)
from routers import auth, investments, credit_cards, bank_accounts, dashboard, suggestions, export, pdf_import, categories, imports_auto, insights, transactions

# Now create bank_transactions table too
from routers.bank_accounts import BankTransaction
Base.metadata.create_all(bind=engine)


def run_migrations():
    """
    SQLite-safe column additions. create_all() won't add new columns to existing tables,
    so we use ALTER TABLE … ADD COLUMN IF NOT EXISTS (SQLite 3.37+) or try/ignore.
    """
    from sqlalchemy import text
    migrations = [
        # Credit card new fields
        ("credit_cards", "card_number_masked",   "TEXT DEFAULT ''"),
        ("credit_cards", "available_credit",     "FLOAT DEFAULT 0.0"),
        ("credit_cards", "available_cash_limit", "FLOAT DEFAULT 0.0"),
        ("credit_cards", "payment_due_date",     "DATE"),
        ("credit_cards", "statement_date",       "DATE"),
        ("credit_cards", "billing_start",        "DATE"),
        ("credit_cards", "billing_end",          "DATE"),
        # Investment currency tracking
        ("investments",  "currency",             "TEXT DEFAULT 'INR'"),
        ("investments",  "fx_rate",              "FLOAT DEFAULT 0.0"),
        # CC transaction type
        ("credit_card_transactions", "transaction_type", "TEXT DEFAULT 'debit'"),
        # D6 matching flags
        ("credit_card_transactions", "is_reimbursement", "BOOLEAN DEFAULT 0"),
        ("credit_card_transactions", "matched_txn_id",   "INTEGER"),
        ("bank_transactions", "is_self_transfer", "BOOLEAN DEFAULT 0"),
        ("bank_transactions", "is_reimbursement", "BOOLEAN DEFAULT 0"),
        ("bank_transactions", "matched_txn_id",   "INTEGER"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore


run_migrations()

app = FastAPI(title="WealthOS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api. In dev, Vite proxies /api → :8000 unchanged;
# in production the same origin serves both the API and the built frontend,
# so one port (8000) is all a phone needs.
for r in (auth.router, investments.router, credit_cards.router, bank_accounts.router,
          dashboard.router, suggestions.router, export.router, pdf_import.router,
          categories.router, imports_auto.router, insights.router, transactions.router):
    app.include_router(r, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Serve the built frontend (single-service mode) ────────────────────────────
# If frontend/dist exists (run ./start.sh or `npm run build`), the backend
# serves it: open http://<machine>:8000 from any device on your network.
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"))

if os.path.isdir(FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = os.path.realpath(os.path.join(FRONTEND_DIST, full_path))
        if full_path and candidate.startswith(FRONTEND_DIST) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    @app.get("/")
    def root():
        return {"app": "WealthOS", "status": "running", "note": "frontend not built — run ./start.sh",
                "time": datetime.utcnow().isoformat()}
