from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import sys, os, io, csv, re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import CreditCard, CreditCardTransaction
from schemas import CreditCardCreate, CreditCardUpdate, TransactionCreate
from file_utils import decrypt_xlsx_if_needed, load_workbook_rows
from categorizer import load_rules, apply_rules, uncategorized_descriptions

from routers.auth import require_auth

router = APIRouter(prefix="/credit-cards", tags=["credit_cards"], dependencies=[Depends(require_auth)])
MONTHLY_SALARY = 100000

CATEGORY_KEYWORDS = {
    "Food & Dining":   ["zomato","swiggy","domino","pizza","mcdonald","kfc","restaurant","cafe","food","eat","dining","hotel","bar","bake","burger","biryani"],
    "Groceries":       ["bigbasket","grofers","blinkit","zepto","dmart","reliance fresh","more supermarket","supermarket","grocery","vegetables","fruits","milk"],
    "Shopping":        ["amazon","flipkart","myntra","ajio","meesho","nykaa","shoppers stop","lifestyle","max fashion","shopping","mall"],
    "Travel":          ["irctc","makemytrip","goibibo","ola","uber","rapido","metro","bus","train","flight","airline","indigo","spicejet","air india","cab","taxi","auto"],
    "Fuel":            ["petrol","diesel","fuel","hp petrol","indian oil","bharat petroleum","bpcl","hpcl","iocl"],
    "Entertainment":   ["netflix","amazon prime","hotstar","youtube","spotify","bookmyshow","pvr","inox","cinema","movie","theatre","game","gaming"],
    "Healthcare":      ["pharmacy","medical","hospital","clinic","doctor","apollo","fortis","manipal","medplus","netmeds","1mg","pharmeasy","health","lab","diagnostic"],
    "Utilities":       ["electricity","water","gas","internet","broadband","jio","airtel","vodafone","vi ","bsnl","recharge","bill payment","bbps","bescom","tnerc"],
    "Education":       ["coursera","udemy","unacademy","byjus","school","college","university","course","book","stationery"],
    "ATM/Cash":        ["atm withdrawal","cash","atm "],
}

def guess_category(description: str) -> str:
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                return category
    return "Other"

def safe_float(val):
    if val is None: return 0.0
    try: return float(str(val).replace(",","").replace("₹","").replace("Dr","").replace("CR","").strip() or 0)
    except: return 0.0

def parse_date(val) -> datetime:
    if isinstance(val, datetime): return val
    s = str(val).strip()
    for fmt in ["%d-%m-%Y","%d/%m/%Y","%Y-%m-%d","%m/%d/%Y","%d %b %Y","%d-%b-%Y","%d %B %Y","%b %d, %Y","%d-%b-%y"]:
        try: return datetime.strptime(s, fmt)
        except: pass
    return datetime.utcnow()

def enrich_card(card: CreditCard) -> dict:
    # FIX: utilization = total_due / credit_limit (what you actually owe vs limit)
    due = getattr(card, 'total_due', 0) or card.current_balance or 0
    util = (due / card.credit_limit * 100) if card.credit_limit > 0 else 0
    return {
        "id": card.id, "name": card.name, "bank": card.bank,
        "card_number_masked": getattr(card, 'card_number_masked', ''),
        "credit_limit":       card.credit_limit,
        "available_credit":   getattr(card, 'available_credit', 0) or 0,
        "available_cash_limit": getattr(card, 'available_cash_limit', 0) or 0,
        "current_balance":    card.current_balance,   # backward compat
        "total_due":          getattr(card, 'total_due', 0) or 0,
        "minimum_due":        card.minimum_due,
        "payment_due_date":   getattr(card, 'payment_due_date', None),
        "statement_date":     getattr(card, 'statement_date', None),
        "billing_start":      getattr(card, 'billing_start', None),
        "billing_end":        getattr(card, 'billing_end', None),
        "statement_day":      card.statement_day,
        "due_day":            card.due_day,
        "created_at":         card.created_at,
        "utilization_percent": round(util, 2),
        "alert_80":           util >= 80,
    }


@router.get("/")
def get_cards(db: Session = Depends(get_db)):
    return [enrich_card(c) for c in db.query(CreditCard).all()]


@router.post("/")
def create_card(data: CreditCardCreate, db: Session = Depends(get_db)):
    card = CreditCard(**data.model_dump())
    db.add(card); db.commit(); db.refresh(card)
    return enrich_card(card)


@router.put("/{card_id}")
def update_card(card_id: int, data: CreditCardUpdate, db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card: raise HTTPException(status_code=404, detail="Card not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(card, k, v)
    db.commit(); db.refresh(card)
    return enrich_card(card)


@router.delete("/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card: raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card); db.commit()
    return {"message": "Deleted"}


@router.get("/{card_id}/transactions")
def get_transactions(card_id: int, month: Optional[int] = None, year: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(CreditCardTransaction).filter(CreditCardTransaction.card_id == card_id)
    if month and year:
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        q = q.filter(CreditCardTransaction.transaction_date >= start,
                     CreditCardTransaction.transaction_date < end)
    return [{"id": t.id, "card_id": t.card_id, "amount": t.amount, "category": t.category,
             "description": t.description, "transaction_date": t.transaction_date,
             "created_at": t.created_at} for t in q.order_by(CreditCardTransaction.transaction_date.desc()).all()]


@router.post("/transactions")
def add_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == data.card_id).first()
    if not card: raise HTTPException(status_code=404, detail="Card not found")
    if data.category:
        cat = data.category
    else:
        desc = data.description or ""
        cat = apply_rules(desc, guess_category(desc), load_rules(db))
    txn = CreditCardTransaction(
        card_id=data.card_id, amount=data.amount, category=cat,
        description=data.description or "",
        transaction_date=data.transaction_date or datetime.utcnow(),
    )
    db.add(txn)
    card.current_balance += data.amount
    db.commit(); db.refresh(txn)
    return {"id": txn.id, "card_id": txn.card_id, "amount": txn.amount,
            "category": txn.category, "description": txn.description,
            "transaction_date": txn.transaction_date, "created_at": txn.created_at}


@router.delete("/transactions/{txn_id}")
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.query(CreditCardTransaction).filter(CreditCardTransaction.id == txn_id).first()
    if not txn: raise HTTPException(status_code=404, detail="Not found")
    card = db.query(CreditCard).filter(CreditCard.id == txn.card_id).first()
    if card: card.current_balance -= txn.amount
    db.delete(txn); db.commit()
    return {"message": "Deleted"}


@router.get("/spending-summary")
def spending_summary(month: Optional[int] = None, year: Optional[int] = None, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    m, y = month or now.month, year or now.year
    start = datetime(y, m, 1)
    end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    txns = db.query(CreditCardTransaction).filter(
        CreditCardTransaction.transaction_date >= start,
        CreditCardTransaction.transaction_date < end,
        CreditCardTransaction.transaction_type == "debit").all()
    total = sum(t.amount for t in txns)
    by_cat = {}
    by_card = {}
    for t in txns:
        by_cat[t.category] = by_cat.get(t.category, 0) + t.amount
        by_card[t.card_id] = by_card.get(t.card_id, 0) + t.amount
    pct = (total / MONTHLY_SALARY * 100) if MONTHLY_SALARY > 0 else 0
    alerts = []
    if pct >= 40: alerts.append({"type": "warning", "message": f"CC spend ₹{total:,.0f} is {pct:.0f}% of monthly salary"})
    if total > MONTHLY_SALARY: alerts.append({"type": "danger", "message": "Total CC spend exceeds monthly salary!"})
    for card in db.query(CreditCard).all():
        due = (card.total_due or card.current_balance or 0)
        u = (due / card.credit_limit * 100) if card.credit_limit else 0
        if u >= 80: alerts.append({"type": "warning", "message": f"{card.name}: {u:.0f}% utilization"})
    return {"total_spend": round(total, 2), "salary_percent": round(pct, 2),
            "by_category": {k: round(v, 2) for k, v in by_cat.items()},
            "by_card": {str(k): round(v, 2) for k, v in by_card.items()},
            "alerts": alerts, "month": m, "year": y}


def _parse_xlsx_statement(content: bytes, card_id: int) -> list:
    """Universal XLSX CC statement parser — handles HDFC, Axis, CSB formats"""
    rows = load_workbook_rows(content)

    # Find header row by looking for Date + Description/Narration + Amount columns
    header_row_idx = None
    date_col = desc_col = amount_col = dr_cr_col = None

    for i, row in enumerate(rows):
        if not row: continue
        cells = [str(c).strip().lower() if c else "" for c in row]
        has_date   = any("date" in c for c in cells)
        has_desc   = any(any(x in c for x in ["description","narration","particulars","details","merchant"]) for c in cells)
        has_amount = any("amount" in c for c in cells)
        if has_date and (has_desc or has_amount):
            header_row_idx = i
            # Map columns
            for j, c in enumerate(cells):
                if "date" in c and date_col is None: date_col = j
                if any(x in c for x in ["description","narration","particulars","details","merchant"]) and desc_col is None: desc_col = j
                if "amount" in c and amount_col is None: amount_col = j
                if any(x in c for x in ["debit","dr "]) and dr_cr_col is None: dr_cr_col = ("debit", j)
                if any(x in c for x in ["credit","cr "]) and dr_cr_col is None and "debit" not in c: dr_cr_col = ("credit", j)
            break

    if header_row_idx is None:
        raise ValueError("Could not find header row with Date and Description/Amount columns")

    txns = []
    for row in rows[header_row_idx + 1:]:
        if not row or not any(row): continue

        raw_date = row[date_col] if date_col is not None else None
        raw_desc = str(row[desc_col]).strip() if desc_col is not None and row[desc_col] else ""
        raw_amt  = row[amount_col] if amount_col is not None else None

        if not raw_date and not raw_desc: continue

        amount = safe_float(raw_amt)

        # Some statements have separate Debit/Credit columns
        if amount == 0 and dr_cr_col:
            col_type, col_idx = dr_cr_col
            amount = safe_float(row[col_idx]) if col_idx < len(row) else 0

        if amount == 0: continue

        # Skip credit/payment rows (negative = payment received)
        desc_low = raw_desc.lower()
        if any(x in desc_low for x in ["payment received","payment thank","credit adjustment","refund"]):
            continue

        txn_date = parse_date(raw_date) if raw_date else datetime.utcnow()
        category = guess_category(raw_desc)

        txns.append({
            "card_id": card_id, "amount": abs(amount),
            "description": raw_desc, "category": category,
            "transaction_date": txn_date,
        })

    return txns


def _parse_csv_statement(content: bytes, card_id: int) -> list:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    txns = []
    for row in reader:
        keys = {k.lower().strip(): v for k, v in row.items()}
        desc = keys.get("description") or keys.get("narration") or keys.get("particulars") or keys.get("details") or ""
        amt_key = next((k for k in keys if "amount" in k or "debit" in k), None)
        date_key = next((k for k in keys if "date" in k), None)
        amount = safe_float(keys.get(amt_key, 0)) if amt_key else 0
        if amount == 0: continue
        txn_date = parse_date(keys[date_key]) if date_key and keys.get(date_key) else datetime.utcnow()
        txns.append({"card_id": card_id, "amount": abs(amount),
                     "description": str(desc).strip(), "category": guess_category(str(desc)),
                     "transaction_date": txn_date})
    return txns


@router.post("/{card_id}/import-statement")
async def import_statement(card_id: int, file: UploadFile = File(...),
                           password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """
    Import CC statement from XLSX or CSV (password-protected XLSX supported).
    Auto-detects format. Works with HDFC, Axis, CSB bank exports.
    Auto-categorizes transactions — learned rules first, then merchant keywords.
    """
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card: raise HTTPException(status_code=404, detail="Card not found")

    content = await file.read()
    content = decrypt_xlsx_if_needed(content, password)
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            txn_data = _parse_xlsx_statement(content, card_id)
        else:
            try:
                txn_data = _parse_xlsx_statement(content, card_id)
            except Exception:
                txn_data = _parse_csv_statement(content, card_id)

        if not txn_data:
            raise HTTPException(status_code=400, detail="No debit transactions found. Check if the file has the right format.")

        rules = load_rules(db)
        for t in txn_data:
            t["category"] = apply_rules(t["description"], t["category"], rules)

        imported = 0
        total_amount = 0
        for t in txn_data:
            txn = CreditCardTransaction(**t)
            db.add(txn)
            total_amount += t["amount"]
            imported += 1

        # Update card balance to reflect imported transactions
        card.current_balance = total_amount
        db.commit()

        # Category breakdown
        by_cat = {}
        for t in txn_data:
            by_cat[t["category"]] = by_cat.get(t["category"], 0) + t["amount"]

        return {
            "message": f"Imported {imported} transactions totalling ₹{total_amount:,.2f}",
            "imported": imported,
            "total_amount": round(total_amount, 2),
            "category_breakdown": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda x: -x[1])},
            "sample": [{"date": str(t["transaction_date"].date()), "desc": t["description"][:50],
                        "amount": t["amount"], "category": t["category"]} for t in txn_data[:5]],
            "uncategorized": uncategorized_descriptions(txn_data),
        }

    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")


# Keep old endpoint for compatibility
@router.post("/{card_id}/import-csv")
async def import_csv_compat(card_id: int, file: UploadFile = File(...),
                            password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return await import_statement(card_id=card_id, file=file, password=password, db=db)
