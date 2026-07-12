"""CR11: unified transaction search + inline category edit (with learning)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import CreditCardTransaction, CreditCard, BankAccount, CategoryRule
from routers.auth import require_auth
from routers.bank_accounts import BankTransaction

router = APIRouter(prefix="/transactions", tags=["transactions"], dependencies=[Depends(require_auth)])


@router.get("/search")
def search(q: str, limit: int = 50, db: Session = Depends(get_db)):
    q = (q or "").strip()
    if len(q) < 2:
        raise HTTPException(400, "Type at least 2 characters")
    like = f"%{q.lower()}%"
    amount = None
    try:
        amount = float(q.replace(",", ""))
    except ValueError:
        pass

    acc_names = {a.id: a.name for a in db.query(BankAccount).all()}
    card_names = {c.id: c.name for c in db.query(CreditCard).all()}
    out = []

    bq = db.query(BankTransaction).filter(or_(
        func.lower(BankTransaction.description).like(like),
        *( [BankTransaction.debit_amount == amount, BankTransaction.credit_amount == amount] if amount is not None else [] )
    )).order_by(BankTransaction.transaction_date.desc()).limit(limit)
    for t in bq:
        out.append({"source": "bank", "id": t.id, "where": acc_names.get(t.account_id, "?"),
                    "date": t.transaction_date, "description": t.description,
                    "debit": t.debit_amount, "credit": t.credit_amount,
                    "category": t.category, "is_self_transfer": t.is_self_transfer,
                    "is_reimbursement": t.is_reimbursement})

    cq = db.query(CreditCardTransaction).filter(or_(
        func.lower(CreditCardTransaction.description).like(like),
        *( [CreditCardTransaction.amount == amount] if amount is not None else [] )
    )).order_by(CreditCardTransaction.transaction_date.desc()).limit(limit)
    for t in cq:
        out.append({"source": "cc", "id": t.id, "where": card_names.get(t.card_id, "?"),
                    "date": t.transaction_date, "description": t.description,
                    "debit": t.amount if t.transaction_type == "debit" else 0,
                    "credit": t.amount if t.transaction_type != "debit" else 0,
                    "category": t.category, "is_self_transfer": False,
                    "is_reimbursement": t.is_reimbursement})

    out.sort(key=lambda r: r["date"], reverse=True)
    return out[:limit]


class CategoryEdit(BaseModel):
    category: str
    learn: bool = True
    pattern: Optional[str] = None


@router.put("/{source}/{txn_id}/category")
def set_category(source: str, txn_id: int, data: CategoryEdit, db: Session = Depends(get_db)):
    category = data.category.strip()
    if not category:
        raise HTTPException(400, "Category required")
    model = BankTransaction if source == "bank" else CreditCardTransaction if source == "cc" else None
    if model is None:
        raise HTTPException(400, "source must be 'bank' or 'cc'")
    txn = db.query(model).filter(model.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    txn.category = category

    retagged = 0
    if data.learn:
        pattern = (data.pattern or txn.description or "").strip().lower()
        if pattern:
            existing = db.query(CategoryRule).filter(CategoryRule.pattern == pattern).first()
            if existing:
                existing.category = category
            else:
                db.add(CategoryRule(pattern=pattern, category=category))
            retagged += db.query(CreditCardTransaction).filter(
                func.lower(CreditCardTransaction.description).contains(pattern)
            ).update({CreditCardTransaction.category: category}, synchronize_session=False)
            retagged += db.query(BankTransaction).filter(
                func.lower(BankTransaction.description).contains(pattern)
            ).update({BankTransaction.category: category}, synchronize_session=False)
    db.commit()
    return {"message": f"Category set to {category}"
                       + (f" — learned rule retagged {retagged} matching transactions" if data.learn else ""),
            "retagged": retagged}
