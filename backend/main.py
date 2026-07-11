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
from routers import auth, investments, credit_cards, bank_accounts, dashboard, suggestions, export, pdf_import, categories

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

app.include_router(auth.router)
app.include_router(investments.router)
app.include_router(credit_cards.router)
app.include_router(bank_accounts.router)
app.include_router(dashboard.router)
app.include_router(suggestions.router)
app.include_router(export.router)
app.include_router(pdf_import.router)
app.include_router(categories.router)


@app.get("/")
def root():
    return {"app": "WealthOS", "status": "running", "time": datetime.utcnow().isoformat()}

@app.get("/health")
def health():
    return {"status": "ok"}
