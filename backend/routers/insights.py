"""Insights endpoints: spend trend (CR6), statement coverage (CR13),
recurring charges (CR12), anomalies (CR17), interest & fees (CR18),
tax estimate (CR14), approximate returns (CR15), and D6 rematch."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import CreditCardTransaction, CreditCard, BankAccount, Investment
from routers.auth import require_auth
from routers.bank_accounts import BankTransaction
from matching import rematch_all, find_recurring, find_anomalies, find_charges

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(require_auth)])

# Bank debits in these categories are money-movement, not consumption —
# and CC bill payments would double-count the CC transactions themselves.
BANK_SPEND_EXCLUDE = {"Bill Payment", "Investment", "Transfer"}


def _months_back(n=6):
    now = datetime.utcnow()
    out, y, m = [], now.year, now.month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _spendable_bank(db):
    return [t for t in db.query(BankTransaction).all()
            if (t.debit_amount or 0) > 0 and not t.is_self_transfer
            and not t.is_reimbursement and t.category not in BANK_SPEND_EXCLUDE]


def _spendable_cc(db):
    return [t for t in db.query(CreditCardTransaction).all()
            if t.transaction_type == "debit" and not t.is_reimbursement]


@router.get("/spend-trend")
def spend_trend(db: Session = Depends(get_db)):
    """Monthly spend for the last 6 months — CC + bank, D6-aware (self
    transfers, reimbursed expenses and CC bill payments excluded)."""
    months = _months_back(6)
    data = {ym: {"cc": 0.0, "bank": 0.0, "by_category": {}} for ym in months}
    for t in _spendable_cc(db):
        ym = (t.transaction_date.year, t.transaction_date.month)
        if ym in data:
            data[ym]["cc"] += t.amount or 0
            data[ym]["by_category"][t.category] = data[ym]["by_category"].get(t.category, 0) + (t.amount or 0)
    for t in _spendable_bank(db):
        ym = (t.transaction_date.year, t.transaction_date.month)
        if ym in data:
            data[ym]["bank"] += t.debit_amount or 0
            data[ym]["by_category"][t.category] = data[ym]["by_category"].get(t.category, 0) + (t.debit_amount or 0)
    out = []
    for (y, m) in months:
        d = data[(y, m)]
        cats = sorted(d["by_category"].items(), key=lambda x: -x[1])[:5]
        out.append({"month": f"{y}-{m:02d}", "label": datetime(y, m, 1).strftime("%b"),
                    "cc": round(d["cc"], 2), "bank": round(d["bank"], 2),
                    "total": round(d["cc"] + d["bank"], 2),
                    "top_categories": [{"category": c, "amount": round(v, 2)} for c, v in cats]})
    return out


@router.get("/coverage")
def statement_coverage(db: Session = Depends(get_db)):
    """CR13: which months have imported data, per account and card."""
    months = _months_back(6)
    labels = [f"{y}-{m:02d}" for y, m in months]
    bank_seen, cc_seen = {}, {}
    for t in db.query(BankTransaction).all():
        bank_seen.setdefault(t.account_id, set()).add((t.transaction_date.year, t.transaction_date.month))
    for t in db.query(CreditCardTransaction).all():
        cc_seen.setdefault(t.card_id, set()).add((t.transaction_date.year, t.transaction_date.month))
    rows = []
    for a in db.query(BankAccount).all():
        rows.append({"name": a.name, "type": "bank",
                     "months": [((y, m) in bank_seen.get(a.id, set())) for y, m in months]})
    for c in db.query(CreditCard).all():
        rows.append({"name": c.name, "type": "cc",
                     "months": [((y, m) in cc_seen.get(c.id, set())) for y, m in months]})
    return {"months": labels, "rows": rows}


# ── Tax & returns (estimates from holdings; assumptions stated) ───────────────

EQUITY = {"indian_stocks", "mutual_funds"}
LT_365 = EQUITY
TAX_ASSUMPTIONS = [
    "Unrealized gains only — this estimates tax IF you sold everything today.",
    "Holding period approximated from when the holding was first imported into WealthOS.",
    "Equity (Indian stocks/MF): LTCG >1y at 12.5% beyond ₹1.25L exemption; STCG 20%.",
    "US stocks / gold / silver ETFs: LTCG >2y at 12.5%; STCG at slab (30% assumed).",
    "Crypto: flat 30% (VDA), no long-term benefit. SGB held to maturity: exempt.",
    "Verify with a CA before filing — rates as of FY 2025-26.",
]


def _tax_estimate(db):
    now = datetime.utcnow()
    per_class, eq_lt_gain, total_tax = {}, 0.0, 0.0
    invs = db.query(Investment).all()
    for i in invs:
        gain = (i.current_value or 0) - (i.invested_amount or 0)
        days = max((now - (i.created_at or now)).days, 0)
        ac = i.asset_class
        row = per_class.setdefault(ac, {"asset_class": ac, "invested": 0, "current": 0,
                                        "gain": 0, "est_tax": 0, "term": ""})
        row["invested"] += i.invested_amount or 0
        row["current"] += i.current_value or 0
        row["gain"] += gain
        if gain <= 0:
            continue
        if ac == "crypto":
            row["est_tax"] += gain * 0.30
            row["term"] = "flat 30%"
        elif ac == "sgb":
            row["term"] = "exempt at maturity"
        elif ac in EQUITY:
            if days >= 365:
                eq_lt_gain += gain
                row["term"] = "LTCG 12.5%"
            else:
                row["est_tax"] += gain * 0.20
                row["term"] = "STCG 20%"
        else:
            if days >= 730:
                row["est_tax"] += gain * 0.125
                row["term"] = "LTCG 12.5%"
            else:
                row["est_tax"] += gain * 0.30
                row["term"] = "STCG ~slab"
    eq_lt_taxable = max(0.0, eq_lt_gain - 125000)
    eq_lt_tax = eq_lt_taxable * 0.125
    rows = [{**r, "invested": round(r["invested"], 2), "current": round(r["current"], 2),
             "gain": round(r["gain"], 2), "est_tax": round(r["est_tax"], 2)}
            for r in per_class.values()]
    total_tax = sum(r["est_tax"] for r in rows) + eq_lt_tax
    return {"rows": sorted(rows, key=lambda r: -abs(r["gain"])),
            "equity_ltcg_gain": round(eq_lt_gain, 2),
            "equity_ltcg_exemption_used": round(min(eq_lt_gain, 125000), 2),
            "equity_ltcg_tax": round(eq_lt_tax, 2),
            "total_estimated_tax": round(total_tax, 2),
            "assumptions": TAX_ASSUMPTIONS}


def _returns(db):
    now = datetime.utcnow()
    rows = []
    for i in db.query(Investment).all():
        inv, cv = i.invested_amount or 0, i.current_value or 0
        if inv <= 0 or cv <= 0:
            continue
        days = max((now - (i.created_at or now)).days, 30)
        annualized = (cv / inv) ** (365.0 / days) - 1
        rows.append({"name": i.name, "asset_class": i.asset_class,
                     "abs_return_pct": round((cv - inv) / inv * 100, 2),
                     "annualized_pct": round(annualized * 100, 2), "days_held": days})
    rows.sort(key=lambda r: -r["annualized_pct"])
    overall = None
    invs = [i for i in db.query(Investment).all() if (i.invested_amount or 0) > 0]
    ti = sum(i.invested_amount for i in invs)
    tc = sum(i.current_value or 0 for i in invs)
    if ti > 0:
        overall = round((tc - ti) / ti * 100, 2)
    return {"note": "Annualized figures approximate — based on first-import date, not true XIRR cash flows.",
            "overall_abs_pct": overall, "best": rows[:3], "worst": rows[-3:][::-1] if len(rows) > 3 else []}


@router.get("/summary")
def insights_summary(db: Session = Depends(get_db)):
    """One call for the Insights page: recurring, anomalies, charges, tax, returns."""
    bank_items = [(t.transaction_date, t.debit_amount or 0, t.description or "")
                  for t in _spendable_bank(db)]
    cc_items = [(t.transaction_date, t.amount or 0, t.description or "")
                for t in _spendable_cc(db)]
    anomaly_items = ([(d, a, s, "bank") for d, a, s in bank_items]
                     + [(d, a, s, "card") for d, a, s in cc_items])
    return {
        "recurring": find_recurring(bank_items + cc_items),
        "anomalies": find_anomalies(anomaly_items),
        "charges": find_charges(db.query(CreditCardTransaction).all()),
        "tax": _tax_estimate(db),
        "returns": _returns(db),
    }


@router.post("/rematch")
def rematch(db: Session = Depends(get_db)):
    """Recompute self-transfer and reimbursement matching over all data."""
    out = rematch_all(db)
    db.commit()
    return {"message": f"Matched {out['self_transfers']} self-transfers and "
                       f"{out['reimbursements']} reimbursements", **out}
