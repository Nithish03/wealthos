from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Session, relationship
from typing import List, Optional
from datetime import datetime
import sys, os, io, csv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db, Base
from models import BankAccount
from schemas import BankAccountCreate, BankAccountUpdate
from file_utils import decrypt_xlsx_if_needed, load_workbook_rows
from categorizer import load_rules, apply_rules, uncategorized_descriptions

from routers.auth import require_auth

router = APIRouter(prefix="/bank-accounts", tags=["bank_accounts"], dependencies=[Depends(require_auth)])
MONTHLY_SALARY = 89200  # in-hand cash (excl. ₹8,800 food card)

# ── BankTransaction model (defined inline to avoid circular imports) ──────────
class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = {'extend_existing': True}
    id               = Column(Integer, primary_key=True, index=True)
    account_id       = Column(Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False)
    transaction_date = Column(DateTime, default=datetime.utcnow)
    description      = Column(String, default="")
    debit_amount     = Column(Float, default=0.0)
    credit_amount    = Column(Float, default=0.0)
    balance          = Column(Float, default=0.0)   # closing balance after txn
    category         = Column(String, default="Other")
    reference        = Column(String, default="")
    is_self_transfer = Column(Boolean, default=False)
    is_reimbursement = Column(Boolean, default=False)
    matched_txn_id   = Column(Integer, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)


CATEGORY_KEYWORDS = {
    "Salary":        ["salary","sal credit","neft cr","imps cr"],
    "Food & Dining": ["zomato","swiggy","domino","pizza","mcdonald","kfc","restaurant","cafe","food","dining","hotel","bake","burger","biryani"],
    "Groceries":     ["bigbasket","grofers","blinkit","zepto","dmart","reliance fresh","grocery","vegetables","milk"],
    "Shopping":      ["amazon","flipkart","myntra","ajio","meesho","nykaa","shopping","mall"],
    "Travel":        ["irctc","makemytrip","goibibo","ola","uber","rapido","metro","train","flight","airline","indigo","spicejet","cab","taxi"],
    "Fuel":          ["petrol","diesel","fuel","hp petrol","indian oil","bpcl","hpcl","iocl"],
    "Entertainment": ["netflix","amazon prime","hotstar","youtube","spotify","bookmyshow","pvr","inox","cinema","movie"],
    "Healthcare":    ["pharmacy","medical","hospital","clinic","doctor","apollo","fortis","medplus","netmeds","1mg","health","lab"],
    "Utilities":     ["electricity","water","gas","internet","broadband","jio","airtel","vodafone","bsnl","recharge","bill payment","bescom"],
    "Education":     ["coursera","udemy","unacademy","byjus","school","college","course","book"],
    "Investment":    ["groww","zerodha","indmoney","coinswitch","mutual fund","nps","ppf","sip","demat"],
    "ATM":           ["atm withdrawal","cash withdrawal","atm "],
    # NOTE: no bare "upi" here — nearly every Indian bank txn is UPI, and a
    # bare match would swallow everything into Transfer. Unknown UPI merchants
    # should stay "Other" so the category trainer can learn them.
    "Transfer":      ["neft","imps","rtgs","transfer","sent to","received from","trf","self trf"],
}

def guess_category(desc: str) -> str:
    d = desc.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in d:
                return cat
    return "Other"

def safe_float(val) -> float:
    if val is None: return 0.0
    try: return abs(float(str(val).replace(",","").replace("₹","").replace("Dr","").replace("CR","").strip() or 0))
    except: return 0.0

def parse_date(val) -> datetime:
    if isinstance(val, datetime): return val
    s = str(val).strip()
    for fmt in ["%d-%m-%Y","%d/%m/%Y","%Y-%m-%d","%m/%d/%Y","%d %b %Y","%d-%b-%Y","%d-%b-%y","%d %B %Y","%b %d, %Y"]:
        try: return datetime.strptime(s, fmt)
        except: pass
    return datetime.utcnow()


def enrich(acc: BankAccount) -> dict:
    em_months = round(acc.balance / MONTHLY_SALARY, 1) if MONTHLY_SALARY > 0 else 0
    return {
        "id": acc.id, "name": acc.name, "bank": acc.bank, "purpose": acc.purpose,
        "balance": acc.balance, "monthly_inflow": acc.monthly_inflow,
        "monthly_outflow": acc.monthly_outflow, "is_emergency_fund": acc.is_emergency_fund,
        "last_updated": acc.last_updated, "created_at": acc.created_at,
        "emergency_alert": acc.is_emergency_fund and acc.balance < MONTHLY_SALARY * 3,
        "emergency_months": em_months,
    }


@router.get("/")
def get_accounts(db: Session = Depends(get_db)):
    return [enrich(a) for a in db.query(BankAccount).all()]


@router.post("/")
def create_account(data: BankAccountCreate, db: Session = Depends(get_db)):
    acc = BankAccount(**data.model_dump())
    db.add(acc); db.commit(); db.refresh(acc)
    return enrich(acc)


@router.put("/{acc_id}")
def update_account(acc_id: int, data: BankAccountUpdate, db: Session = Depends(get_db)):
    acc = db.query(BankAccount).filter(BankAccount.id == acc_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(acc, k, v)
    acc.last_updated = datetime.utcnow()
    db.commit(); db.refresh(acc)
    return enrich(acc)


@router.delete("/{acc_id}")
def delete_account(acc_id: int, db: Session = Depends(get_db)):
    acc = db.query(BankAccount).filter(BankAccount.id == acc_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Not found")
    # delete transactions
    db.query(BankTransaction).filter(BankTransaction.account_id == acc_id).delete()
    db.delete(acc); db.commit()
    return {"message": "Deleted"}


@router.get("/summary")
def account_summary(db: Session = Depends(get_db)):
    accounts = db.query(BankAccount).all()
    total    = sum(a.balance for a in accounts)
    em_bal   = sum(a.balance for a in accounts if a.is_emergency_fund)
    em_months = em_bal / MONTHLY_SALARY if MONTHLY_SALARY > 0 else 0
    net_flow  = sum(a.monthly_inflow - a.monthly_outflow for a in accounts)
    return {
        "total_balance":     round(total, 2),
        "emergency_balance": round(em_bal, 2),
        "emergency_months":  round(em_months, 1),
        "emergency_adequate": em_months >= 3,
        "net_monthly_flow":  round(net_flow, 2),
        "accounts":          len(accounts),
    }


@router.get("/{acc_id}/transactions")
def get_transactions(acc_id: int, limit: int = 100, db: Session = Depends(get_db)):
    txns = (db.query(BankTransaction)
            .filter(BankTransaction.account_id == acc_id)
            .order_by(BankTransaction.transaction_date.desc())
            .limit(limit).all())
    return [{
        "id": t.id, "account_id": t.account_id,
        "transaction_date": t.transaction_date,
        "description": t.description, "debit_amount": t.debit_amount,
        "credit_amount": t.credit_amount, "balance": t.balance,
        "category": t.category, "reference": t.reference,
        "is_self_transfer": t.is_self_transfer, "is_reimbursement": t.is_reimbursement,
    } for t in txns]


def _parse_statement_xlsx(content: bytes, account_id: int):
    rows = load_workbook_rows(content)

    # Find header row — look for Date + (Description/Narration/Particulars) + Amount
    header_idx = None
    date_col = desc_col = debit_col = credit_col = bal_col = ref_col = None

    for i, row in enumerate(rows):
        if not row or not any(c for c in row if c): continue
        cells = [str(c).strip().lower() if c else "" for c in row]
        has_date = any("date" in c for c in cells)
        has_desc = any(any(x in c for x in ["description","narration","particulars","details","transaction","remarks"]) for c in cells)
        has_amt  = any(any(x in c for x in ["amount","debit","credit","dr","cr","withdrawal","deposit"]) for c in cells)
        if has_date and (has_desc or has_amt):
            header_idx = i
            for j, c in enumerate(cells):
                if "date" in c and date_col is None: date_col = j
                if any(x in c for x in ["description","narration","particulars","details","remarks"]) and desc_col is None: desc_col = j
                if any(x in c for x in ["debit","withdrawal","dr ","dr."]) and debit_col is None: debit_col = j
                if any(x in c for x in ["credit","deposit","cr ","cr."]) and credit_col is None: credit_col = j
                if "balance" in c and bal_col is None: bal_col = j
                if any(x in c for x in ["reference","ref","chq","cheque","utr"]) and ref_col is None: ref_col = j
                # Generic amount column (single amount col — check sign or separate debit/credit)
                if "amount" in c and debit_col is None and credit_col is None: debit_col = j
            break

    if header_idx is None:
        raise ValueError("Could not find header row. Expected columns: Date, Description/Narration, Debit/Credit/Amount")

    txns = []
    for row in rows[header_idx + 1:]:
        if not row or not any(c for c in row if c): continue

        raw_date = row[date_col] if date_col is not None and date_col < len(row) else None
        raw_desc = str(row[desc_col]).strip() if desc_col is not None and desc_col < len(row) and row[desc_col] else ""
        raw_deb  = row[debit_col]  if debit_col  is not None and debit_col  < len(row) else None
        raw_cr   = row[credit_col] if credit_col  is not None and credit_col < len(row) else None
        raw_bal  = row[bal_col]    if bal_col     is not None and bal_col    < len(row) else None
        raw_ref  = str(row[ref_col]).strip() if ref_col is not None and ref_col < len(row) and row[ref_col] else ""

        if not raw_date and not raw_desc: continue

        debit  = safe_float(raw_deb)
        credit = safe_float(raw_cr)
        bal    = safe_float(raw_bal)
        txn_date = parse_date(raw_date) if raw_date else datetime.utcnow()

        if debit == 0 and credit == 0: continue

        txns.append({
            "account_id": account_id,
            "transaction_date": txn_date,
            "description": raw_desc,
            "debit_amount": debit,
            "credit_amount": credit,
            "balance": bal,
            "category": guess_category(raw_desc),
            "reference": raw_ref,
        })

    return txns


def _parse_statement_csv(content: bytes, account_id: int):
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    txns = []
    for row in reader:
        keys = {k.strip().lower(): v for k, v in row.items()}
        date_key = next((k for k in keys if "date" in k), None)
        desc_key = next((k for k in keys if any(x in k for x in ["description","narration","particulars","details"])), None)
        # exact-word match for dr/cr — a bare "cr" substring matches "desCRiption"
        deb_key  = next((k for k in keys if k in ("dr", "dr.") or "debit" in k or "withdrawal" in k), None)
        cr_key   = next((k for k in keys if k in ("cr", "cr.") or "credit" in k or "deposit" in k), None)
        bal_key  = next((k for k in keys if "balance" in k), None)
        amt_key  = next((k for k in keys if "amount" in k), None) if not deb_key else None

        desc   = str(keys.get(desc_key,"")).strip()
        debit  = safe_float(keys.get(deb_key  or amt_key, 0))
        credit = safe_float(keys.get(cr_key, 0))
        bal    = safe_float(keys.get(bal_key, 0))
        txn_date = parse_date(keys[date_key]) if date_key and keys.get(date_key) else datetime.utcnow()

        if debit == 0 and credit == 0: continue

        txns.append({
            "account_id": account_id,
            "transaction_date": txn_date,
            "description": desc,
            "debit_amount": debit,
            "credit_amount": credit,
            "balance": bal,
            "category": guess_category(desc),
            "reference": "",
        })
    return txns


@router.post("/{acc_id}/import-statement")
async def import_statement(acc_id: int, file: UploadFile = File(...),
                           password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """
    Import bank statement XLSX or CSV (password-protected XLSX supported).
    Auto-detects Jupiter, DBS, Equitas formats.
    Auto-categorizes transactions — learned rules first, then keywords.
    Updates account balance to latest closing balance.
    """
    acc = db.query(BankAccount).filter(BankAccount.id == acc_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Account not found")

    content  = await file.read()
    content  = decrypt_xlsx_if_needed(content, password)
    filename = (file.filename or "").lower()

    try:
        if filename.endswith((".xlsx", ".xls")):
            txn_data = _parse_statement_xlsx(content, acc_id)
        else:
            try:    txn_data = _parse_statement_xlsx(content, acc_id)
            except: txn_data = _parse_statement_csv(content, acc_id)

        if not txn_data:
            raise HTTPException(status_code=400, detail="No transactions found. Check file format.")

        # each txn dict carries account_id; the shared applier adds it itself
        for t in txn_data:
            t.pop("account_id", None)
        latest_balance = 0.0
        latest_date = None
        for t in txn_data:
            if t["balance"] > 0 and (latest_date is None or t["transaction_date"] > latest_date):
                latest_date, latest_balance = t["transaction_date"], t["balance"]
        from matching import apply_bank_import
        return apply_bank_import({"txns": txn_data, "closing": latest_balance,
                                  "bank": "Excel/CSV statement"}, acc, db)

    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")
