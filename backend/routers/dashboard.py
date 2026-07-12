from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import Investment, CreditCard, BankAccount, NetWorthSnapshot, CreditCardTransaction

from routers.auth import require_auth

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])

MONTHLY_SALARY = 89200  # in-hand cash (excl. ₹8,800 food card)
ANNUAL_CTC = 1395565


def _auto_snapshot(db: Session):
    """CR8: first dashboard visit each month records a net-worth snapshot."""
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    if db.query(NetWorthSnapshot).filter(NetWorthSnapshot.snapshot_date >= month_start).first():
        return
    investments = db.query(Investment).all()
    cards = db.query(CreditCard).all()
    accounts = db.query(BankAccount).all()
    iv = sum((i.current_value or 0) for i in investments)
    bb = sum((a.balance or 0) for a in accounts)
    cd = sum((c.total_due or 0) for c in cards)
    db.add(NetWorthSnapshot(total_assets=iv + bb, total_liabilities=cd, net_worth=iv + bb - cd,
                            investment_value=iv, bank_balance=bb, credit_dues=cd,
                            notes="auto (monthly)"))
    db.commit()


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    _auto_snapshot(db)
    investments = db.query(Investment).all()
    cards = db.query(CreditCard).all()
    accounts = db.query(BankAccount).all()

    total_investments = sum((i.current_value or 0) for i in investments)
    total_bank = sum((a.balance or 0) for a in accounts)
    total_dues = sum((c.total_due or 0) for c in cards)  # FIX: use total_due (statement amount), not current_balance
    total_assets = total_investments + total_bank
    net_worth = total_assets - total_dues

    total_invested = sum((i.invested_amount or 0) for i in investments)
    total_pnl = total_investments - total_invested
    pnl_percent = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    now = datetime.utcnow()
    m, y = now.month, now.year
    start = datetime(y, m, 1)
    end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    monthly_spend = sum(
        t.amount for t in db.query(CreditCardTransaction).filter(
            CreditCardTransaction.transaction_date >= start,
            CreditCardTransaction.transaction_date < end,
            CreditCardTransaction.transaction_type == "debit",
        ).all()
    )

    alerts = []
    spend_pct = (monthly_spend / MONTHLY_SALARY * 100) if MONTHLY_SALARY > 0 else 0
    if spend_pct >= 40:
        alerts.append({"type": "warning", "icon": "💳", "message": f"CC spend is {spend_pct:.0f}% of monthly salary"})
    for card in cards:
        util = ((card.total_due or 0) / card.credit_limit * 100) if card.credit_limit else 0  # FIX: total_due
        if util >= 80:
            alerts.append({"type": "danger", "icon": "🚨", "message": f"{card.name}: {util:.0f}% utilization"})
    for acc in accounts:
        if acc.is_emergency_fund and acc.balance < MONTHLY_SALARY * 3:
            months = acc.balance / MONTHLY_SALARY if MONTHLY_SALARY > 0 else 0
            alerts.append({"type": "warning", "icon": "🏦", "message": f"Emergency fund only covers {months:.1f} months"})

    return {
        "net_worth": round(net_worth, 2),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_dues, 2),
        "investment_value": round(total_investments, 2),
        "total_invested": round(total_invested, 2),
        "total_pnl": round(total_pnl, 2),
        "pnl_percent": round(pnl_percent, 2),
        "bank_balance": round(total_bank, 2),
        "credit_dues": round(total_dues, 2),
        "monthly_spend": round(monthly_spend, 2),
        "spend_salary_percent": round(spend_pct, 2),
        "alerts": alerts,
        "monthly_salary": MONTHLY_SALARY,
        "annual_ctc": ANNUAL_CTC,
    }


@router.get("/net-worth-history")
def get_net_worth_history(db: Session = Depends(get_db)):
    snapshots = db.query(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date.asc()).all()
    return [
        {
            "date": s.snapshot_date.strftime("%Y-%m"),
            "net_worth": s.net_worth,
            "assets": s.total_assets,
            "liabilities": s.total_liabilities,
            "investments": s.investment_value,
            "bank": s.bank_balance,
        }
        for s in snapshots
    ]


@router.post("/snapshot")
def take_snapshot(db: Session = Depends(get_db)):
    investments = db.query(Investment).all()
    cards = db.query(CreditCard).all()
    accounts = db.query(BankAccount).all()

    investment_value = sum((i.current_value or 0) for i in investments)
    bank_balance = sum((a.balance or 0) for a in accounts)
    credit_dues = sum((c.total_due or 0) for c in cards)  # FIX
    total_assets = investment_value + bank_balance
    net_worth = total_assets - credit_dues

    snap = NetWorthSnapshot(
        total_assets=total_assets,
        total_liabilities=credit_dues,
        net_worth=net_worth,
        investment_value=investment_value,
        bank_balance=bank_balance,
        credit_dues=credit_dues,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return {"message": "Snapshot saved", "net_worth": net_worth, "date": snap.snapshot_date}
