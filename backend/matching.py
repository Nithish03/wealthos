"""Domain logic for transaction intelligence (handoff rule D6 and friends):

- import de-duplication (append-safe statement uploads)
- self-transfer detection (Equitas→Jupiter must never double-count)
- reimbursement matching (credits tied back to the originating expense)
- recurring-charge / subscription detection
- anomaly detection (unusually large or duplicate charges)
- interest & fees watchdog

ORM classes are imported lazily inside functions to avoid circular imports
(BankTransaction lives inside routers.bank_accounts).
"""
import re
from datetime import datetime, timedelta


# ── Import de-duplication (CR3) ────────────────────────────────────────────────

def _day(d):
    return d.date() if isinstance(d, datetime) else d


def bank_txn_key(date, debit, credit, desc):
    return (_day(date), round(debit or 0, 2), round(credit or 0, 2), (desc or "").strip().lower())


def cc_txn_key(date, amount, desc):
    return (_day(date), round(amount or 0, 2), (desc or "").strip().lower())


def filter_new(parsed, existing_keys, keyfn):
    """Split parsed txn dicts into (new, duplicate_count) against existing keys."""
    new, dups = [], 0
    for t in parsed:
        k = keyfn(t)
        if k in existing_keys:
            dups += 1
        else:
            existing_keys.add(k)
            new.append(t)
    return new, dups


# ── Self-transfers & reimbursements (CR5 / D6) ────────────────────────────────

def rematch_all(db):
    """Recompute self-transfer and reimbursement flags over ALL transactions.
    Cheap at personal-data scale; called after every import."""
    from routers.bank_accounts import BankTransaction
    from models import CreditCardTransaction

    bank = db.query(BankTransaction).all()
    for t in bank:
        t.is_self_transfer = False
        t.is_reimbursement = False
        t.matched_txn_id = None

    debits = [t for t in bank if (t.debit_amount or 0) > 0]
    credits = [t for t in bank if (t.credit_amount or 0) > 0]

    # Self-transfer: debit in one account, equal credit in ANOTHER account, ≤2 days apart
    used, n_self = set(), 0
    for d in debits:
        cands = [c for c in credits
                 if c.id not in used and c.account_id != d.account_id
                 and abs((c.credit_amount or 0) - (d.debit_amount or 0)) <= 0.5
                 and abs((c.transaction_date - d.transaction_date).days) <= 2]
        if not cands:
            continue
        c = min(cands, key=lambda c: abs((c.transaction_date - d.transaction_date).days))
        used.add(c.id)
        d.is_self_transfer = c.is_self_transfer = True
        d.matched_txn_id, c.matched_txn_id = c.id, d.id
        n_self += 1

    # Bank reimbursement: credit equal to an EARLIER debit in the SAME account within 45 days
    n_reimb, used_deb = 0, set()
    for c in sorted((t for t in credits if not t.is_self_transfer), key=lambda t: t.transaction_date):
        cands = [d for d in debits
                 if d.id not in used_deb and not d.is_self_transfer
                 and d.account_id == c.account_id
                 and abs((d.debit_amount or 0) - (c.credit_amount or 0)) <= 0.5
                 and 0 <= (c.transaction_date - d.transaction_date).days <= 45]
        if not cands:
            continue
        d = max(cands, key=lambda d: d.transaction_date)
        used_deb.add(d.id)
        c.is_reimbursement = d.is_reimbursement = True
        c.matched_txn_id, d.matched_txn_id = d.id, c.id
        n_reimb += 1

    # CC reimbursement: credit txn equal to an earlier debit on the SAME card within 45 days
    cc = db.query(CreditCardTransaction).all()
    for t in cc:
        t.is_reimbursement = False
        t.matched_txn_id = None
    cc_deb = [t for t in cc if t.transaction_type == "debit"]
    used_deb = set()
    for c in sorted((t for t in cc if t.transaction_type == "credit"), key=lambda t: t.transaction_date):
        cands = [d for d in cc_deb
                 if d.id not in used_deb and d.card_id == c.card_id
                 and abs((d.amount or 0) - (c.amount or 0)) <= 0.5
                 and 0 <= (c.transaction_date - d.transaction_date).days <= 45]
        if not cands:
            continue
        d = max(cands, key=lambda d: d.transaction_date)
        used_deb.add(d.id)
        c.is_reimbursement = d.is_reimbursement = True
        c.matched_txn_id, d.matched_txn_id = d.id, c.id
        n_reimb += 1

    return {"self_transfers": n_self, "reimbursements": n_reimb}


# ── Shared import persistence (used by PDF, XLSX/CSV and auto-import) ─────────

def apply_bank_import(result, acc, db):
    """Append-with-dedup a parsed bank statement into an account (CR3)."""
    from routers.bank_accounts import BankTransaction
    from categorizer import load_rules, apply_rules, uncategorized_descriptions

    txns = result["txns"]
    rules = load_rules(db)
    for t in txns:
        t["category"] = apply_rules(t["description"], t["category"], rules)

    existing = db.query(BankTransaction).filter(BankTransaction.account_id == acc.id).all()
    keys = {bank_txn_key(t.transaction_date, t.debit_amount, t.credit_amount, t.description) for t in existing}
    new, dups = filter_new(txns, keys,
                           lambda t: bank_txn_key(t["transaction_date"], t["debit_amount"],
                                                  t["credit_amount"], t["description"]))
    total_d = sum(t["debit_amount"] for t in new)
    total_c = sum(t["credit_amount"] for t in new)
    for t in new:
        db.add(BankTransaction(account_id=acc.id, **t))

    # Balance: only trust the statement if it covers the newest data we have
    latest_existing = max((t.transaction_date for t in existing), default=None)
    latest_parsed = max((t["transaction_date"] for t in txns), default=None)
    if result.get("closing", 0) > 0 and latest_parsed and \
            (latest_existing is None or latest_parsed >= latest_existing):
        acc.balance = result["closing"]
    if total_c > 0: acc.monthly_inflow = round(total_c, 2)
    if total_d > 0: acc.monthly_outflow = round(total_d, 2)
    acc.last_updated = datetime.utcnow()

    db.flush()
    matched = rematch_all(db)
    db.commit()

    by_cat = {}
    for t in new:
        if t["debit_amount"] > 0:
            by_cat[t["category"]] = by_cat.get(t["category"], 0) + t["debit_amount"]
    top = sorted([{"category": k, "amount": round(v, 2)} for k, v in by_cat.items()],
                 key=lambda x: -x["amount"])[:6]
    dates = [t["transaction_date"] for t in txns]
    period = f"{min(dates).strftime('%d %b')} – {max(dates).strftime('%d %b %Y')}" if dates else "—"
    return {
        "message": f"Imported {len(new)} new transactions"
                   + (f" ({dups} duplicates skipped)" if dups else "")
                   + f" from {result.get('bank', 'statement')}",
        "transactions": len(new), "duplicates_skipped": dups,
        "total_credits": round(total_c, 2), "total_debits": round(total_d, 2),
        "closing_balance": result.get("closing"), "period": period,
        "top_categories": top, "uncategorized": uncategorized_descriptions(new),
        **matched,
    }


def apply_cc_import(result, card, db):
    """Append-with-dedup a parsed CC statement into a card (CR3).
    Updates summary fields (dues/limits/dates) when the statement has them."""
    from models import CreditCardTransaction
    from categorizer import load_rules, apply_rules, uncategorized_descriptions

    txns = [t for t in result["txns"] if t.get("transaction_type") != "payment"]
    rules = load_rules(db)
    for t in txns:
        t["category"] = apply_rules(t["description"], t["category"], rules)

    existing = db.query(CreditCardTransaction).filter(CreditCardTransaction.card_id == card.id).all()
    keys = {cc_txn_key(t.transaction_date, t.amount, t.description) for t in existing}
    new, dups = filter_new(txns, keys,
                           lambda t: cc_txn_key(t["transaction_date"], t["amount"], t["description"]))
    for t in new:
        db.add(CreditCardTransaction(
            card_id=card.id, transaction_date=t["transaction_date"],
            description=t["description"], amount=t["amount"],
            category=t["category"], transaction_type=t.get("transaction_type", "debit"),
        ))

    if result.get("total_due", 0) > 0:
        card.total_due = result["total_due"]; card.current_balance = result["total_due"]
    if result.get("min_due", 0) > 0: card.minimum_due = result["min_due"]
    if result.get("credit_limit", 0) > 0: card.credit_limit = result["credit_limit"]
    if result.get("available_credit", 0) > 0: card.available_credit = result["available_credit"]
    if result.get("available_cash_limit", 0) > 0: card.available_cash_limit = result["available_cash_limit"]
    for f in ("payment_due_date", "statement_date", "billing_start", "billing_end"):
        if result.get(f): setattr(card, f, result[f])

    db.flush()
    matched = rematch_all(db)
    db.commit()

    by_cat = {}
    for t in new:
        by_cat[t["category"]] = by_cat.get(t["category"], 0) + abs(t["amount"])
    top = sorted([{"category": k, "amount": round(v, 2)} for k, v in by_cat.items()],
                 key=lambda x: -x["amount"])[:6]
    return {
        "message": f"Imported {len(new)} new transactions"
                   + (f" ({dups} duplicates skipped)" if dups else "")
                   + f" from {result.get('bank', 'statement')}",
        "transactions": len(new), "duplicates_skipped": dups,
        "total_due": result.get("total_due", 0), "min_due": result.get("min_due", 0),
        "credit_limit": result.get("credit_limit", 0),
        "available_credit": result.get("available_credit", 0),
        "payment_due_date": str(result.get("payment_due_date") or ""),
        "top_categories": top, "uncategorized": uncategorized_descriptions(new),
        **matched,
    }


# ── Recurring charges (CR12) ───────────────────────────────────────────────────

_NOISE = re.compile(r"[\d/\\@#:*_.,-]+")
_STOP = {"upi", "neft", "imps", "rtgs", "ref", "pvt", "ltd", "payment", "pay",
         "txn", "pos", "trf", "the", "and", "for", "www", "com", "india", "bangalore", "mumbai"}


def merchant_key(desc: str) -> str:
    d = _NOISE.sub(" ", (desc or "").lower())
    words = [w for w in d.split() if len(w) > 2 and w not in _STOP]
    return " ".join(words[:3])


def find_recurring(items):
    """items: list of (date, amount, description). Recurring = same merchant in
    ≥3 distinct months with amounts within ~35% of each other."""
    groups = {}
    for date, amount, desc in items:
        k = merchant_key(desc)
        if not k or amount <= 0:
            continue
        groups.setdefault(k, []).append((date, amount, desc))
    out = []
    for k, g in groups.items():
        months = {(x[0].year, x[0].month) for x in g}
        if len(months) < 3:
            continue
        amts = [x[1] for x in g]
        if max(amts) / max(min(amts), 1) > 1.35:
            continue
        g.sort(key=lambda x: x[0])
        out.append({
            "merchant": k, "sample": g[-1][2][:60],
            "avg_amount": round(sum(amts) / len(amts), 2),
            "months_seen": len(months),
            "last_date": g[-1][0].strftime("%d %b %Y"),
        })
    out.sort(key=lambda r: -r["avg_amount"])
    return {"items": out[:20], "monthly_burn": round(sum(r["avg_amount"] for r in out), 2)}


# ── Anomalies (CR17) ───────────────────────────────────────────────────────────

def find_anomalies(items, days=60, now=None):
    """items: (date, amount, description, source_label). Flags recent charges
    ≥3× the merchant's historical average, and same-merchant same-amount
    duplicates within 3 days."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=days)
    history, recent = {}, []
    for date, amount, desc, src in items:
        k = merchant_key(desc)
        if not k or amount <= 0:
            continue
        if date >= cutoff:
            recent.append((date, amount, desc, src, k))
        else:
            history.setdefault(k, []).append(amount)
    alerts = []
    for date, amount, desc, src, k in recent:
        hist = history.get(k, [])
        if len(hist) >= 3 and amount >= 500:
            avg = sum(hist) / len(hist)
            if amount >= 3 * avg:
                alerts.append({"type": "spike", "date": date.strftime("%d %b"), "source": src,
                               "description": desc[:60], "amount": round(amount, 2),
                               "usual": round(avg, 2),
                               "message": f"₹{amount:,.0f} is {amount/avg:.1f}× your usual ₹{avg:,.0f} here"})
    seen = {}
    for date, amount, desc, src, k in sorted(recent, key=lambda x: x[0]):
        dk = (k, round(amount, 2))
        if dk in seen and abs((date - seen[dk]).days) <= 3 and amount >= 100:
            alerts.append({"type": "duplicate", "date": date.strftime("%d %b"), "source": src,
                           "description": desc[:60], "amount": round(amount, 2),
                           "message": f"Possible duplicate charge of ₹{amount:,.0f} within 3 days"})
        seen[dk] = date
    return alerts[:15]


# ── Interest & fees watchdog (CR18) ───────────────────────────────────────────

CHARGE_KEYWORDS = ["emi interest", "interest charge", "finance charge", "gst",
                   "late fee", "latefee", "over limit", "overlimit", "forex", "markup",
                   "annual fee", "joining fee", "processing fee", "renewal fee"]


def find_charges(cc_txns, months=6, now=None):
    """cc_txns: ORM CreditCardTransaction rows. Returns monthly totals of
    interest/fees/GST plus the individual line items."""
    now = now or datetime.utcnow()
    items, monthly = [], {}
    for t in cc_txns:
        if t.transaction_type != "debit":
            continue
        d = (t.description or "").lower()
        if t.category == "Finance Charges" or any(k in d for k in CHARGE_KEYWORDS):
            mk = t.transaction_date.strftime("%Y-%m")
            monthly[mk] = monthly.get(mk, 0) + (t.amount or 0)
            items.append({"date": t.transaction_date.strftime("%d %b %Y"),
                          "description": (t.description or "")[:60],
                          "amount": round(t.amount or 0, 2)})
    keys = sorted(monthly.keys())[-months:]
    items.sort(key=lambda x: x["date"], reverse=True)
    return {"monthly": [{"month": k, "amount": round(monthly[k], 2)} for k in keys],
            "total_6m": round(sum(monthly[k] for k in keys), 2),
            "items": items[:20]}
