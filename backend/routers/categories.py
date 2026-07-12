from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import CategoryRule, CreditCardTransaction
from routers.auth import require_auth
from routers.bank_accounts import BankTransaction

router = APIRouter(prefix="/categories", tags=["categories"], dependencies=[Depends(require_auth)])


class RuleIn(BaseModel):
    pattern: str
    category: str


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    return [
        {"id": r.id, "pattern": r.pattern, "category": r.category, "created_at": r.created_at}
        for r in db.query(CategoryRule).order_by(CategoryRule.pattern).all()
    ]


@router.post("/rules/bulk")
def save_rules(rules: List[RuleIn], db: Session = Depends(get_db)):
    """Save (upsert) learned rules AND retag every existing transaction that
    matches — so teaching once fixes history too."""
    saved = retagged_cc = retagged_bank = 0
    for r in rules:
        pattern = r.pattern.strip().lower()
        category = r.category.strip()
        if not pattern or not category:
            continue
        existing = db.query(CategoryRule).filter(CategoryRule.pattern == pattern).first()
        if existing:
            existing.category = category
        else:
            db.add(CategoryRule(pattern=pattern, category=category))
        saved += 1
        retagged_cc += db.query(CreditCardTransaction).filter(
            func.lower(CreditCardTransaction.description).contains(pattern)
        ).update({CreditCardTransaction.category: category}, synchronize_session=False)
        retagged_bank += db.query(BankTransaction).filter(
            func.lower(BankTransaction.description).contains(pattern)
        ).update({BankTransaction.category: category}, synchronize_session=False)
    db.commit()
    return {
        "message": f"Learned {saved} rule{'s' if saved != 1 else ''} — "
                   f"retagged {retagged_cc + retagged_bank} existing transactions",
        "rules_saved": saved,
        "cc_transactions_retagged": retagged_cc,
        "bank_transactions_retagged": retagged_bank,
    }


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(CategoryRule).filter(CategoryRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Deleted"}
