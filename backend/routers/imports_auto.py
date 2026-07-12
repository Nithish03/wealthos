"""CR1/CR2: universal auto-import. Drop ANY statement file — the backend
figures out what it is (bank / credit card / broker holdings), which
account or card it belongs to (creating one when none exists), and imports
with dedup. When the target is ambiguous it returns 422 target_required
with options so the UI can ask."""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import sys, os, re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import BankAccount, CreditCard, Investment
from file_utils import decrypt_pdf_if_needed, decrypt_xlsx_if_needed, load_workbook_rows
from matching import apply_bank_import, apply_cc_import
from routers.auth import require_auth
from routers import pdf_import as P
from routers import investments as INV
from routers import bank_accounts as BA
from routers import credit_cards as CCR

router = APIRouter(prefix="/import", tags=["auto_import"], dependencies=[Depends(require_auth)])

CC_TEXT_MARKERS = ("total amount due", "minimum amount due", "minimum due",
                   "credit card statement", "credit limit", "billing period")
GENERIC_WORDS = {"bank", "statement", "generic", "auto", "detected", "text", "parser", "card", "credit"}


def _options(kind: str, db: Session):
    if kind == "bank":
        return [{"id": a.id, "name": f"{a.name} ({a.bank})"} for a in db.query(BankAccount).all()]
    return [{"id": c.id, "name": f"{c.name} ({c.bank})"} for c in db.query(CreditCard).all()]


def _need_target(kind: str, db: Session):
    raise HTTPException(status_code=422, detail={
        "code": "target_required", "kind": kind, "options": _options(kind, db),
        "message": f"Detected a {'bank' if kind == 'bank' else 'credit card'} statement, "
                   "but couldn't tell which one it belongs to — pick it.",
    })


def _tokens(label: str):
    return [w for w in re.split(r"[^a-z]+", (label or "").lower())
            if len(w) >= 3 and w not in GENERIC_WORDS]


def _resolve_bank(result, db, target_id):
    if target_id:
        acc = db.query(BankAccount).filter(BankAccount.id == target_id).first()
        if acc:
            return acc, False
    accounts = db.query(BankAccount).all()
    toks = _tokens(result.get("bank", ""))
    if toks:
        matches = [a for a in accounts if any(t in (a.bank + " " + a.name).lower() for t in toks)]
        if len(matches) == 1:
            return matches[0], False
        if not matches:
            label = (result.get("bank") or "Imported Account").replace(" (auto-detected)", "")[:40]
            acc = BankAccount(name=label, bank=label, purpose="auto-created from statement")
            db.add(acc); db.commit(); db.refresh(acc)
            return acc, True
        _need_target("bank", db)          # several accounts match — ask
    # generic parser gave no identifying label: never guess-create
    if len(accounts) == 1:
        return accounts[0], False
    _need_target("bank", db)


def _resolve_card(result, db, target_id):
    if target_id:
        card = db.query(CreditCard).filter(CreditCard.id == target_id).first()
        if card:
            return card, False
    cards = db.query(CreditCard).all()
    last4 = re.sub(r"\D", "", result.get("card_number") or "")[-4:]
    if last4:
        for c in cards:
            if re.sub(r"\D", "", c.card_number_masked or "")[-4:] == last4:
                return c, False
    toks = _tokens(result.get("bank", ""))
    if toks:
        matches = [c for c in cards if any(t in (c.bank + " " + c.name).lower() for t in toks)]
        if len(matches) == 1:
            return matches[0], False
        if not matches:
            label = (result.get("bank") or "Card").replace(" (auto-detected)", "")
            name = f"{label} Card" + (f" •{last4}" if last4 else "")
            card = CreditCard(name=name[:40], bank=label[:40],
                              card_number_masked=result.get("card_number", ""))
            db.add(card); db.commit(); db.refresh(card)
            return card, True
        _need_target("cc", db)   # e.g. two Axis cards and no card number in the file
    if len(cards) == 1:
        return cards[0], False
    _need_target("cc", db)


def _pick_by_filename(entities, fname, db, kind):
    hits = [e for e in entities
            if any(t in fname for t in _tokens(e.bank + " " + e.name) if len(t) >= 4)]
    if len(hits) == 1:
        return hits[0]
    if len(entities) == 1:
        return entities[0]
    _need_target(kind, db)


@router.post("/auto")
async def auto_import(file: UploadFile = File(...), password: Optional[str] = Form(None),
                      kind: Optional[str] = None, target_id: Optional[int] = None,
                      db: Session = Depends(get_db)):
    raw = await file.read()
    fname = (file.filename or "").lower()
    is_pdf = raw[:5] == b"%PDF-" or fname.endswith(".pdf")

    try:
        if is_pdf:
            content = decrypt_pdf_if_needed(raw, password)
            with P.get_pdf_pages(content) as pdf:
                text2 = "\n".join(p.extract_text() or "" for p in pdf.pages[:2]).lower()

            # Broker PDFs first
            if "alpaca" in text2:
                holdings = P.parse_alpaca(content)
                if holdings:
                    db.query(Investment).filter(Investment.platform == "Alpaca").delete()
                    for h in holdings:
                        db.add(Investment(**h))
                    db.commit()
                    return {"kind": "investments", "target": "Alpaca (US stocks)", "created_target": False,
                            "message": f"Imported {len(holdings)} US stock holdings from Alpaca",
                            "transactions": len(holdings), "uncategorized": []}
            if "aura" in text2 and ("gold" in text2 or "silver" in text2):
                holdings = P.parse_aura(content)
                if holdings:
                    db.query(Investment).filter(Investment.platform == "Aura").delete()
                    for h in holdings:
                        db.add(Investment(**h))
                    db.commit()
                    return {"kind": "investments", "target": "Aura (digital metals)", "created_target": False,
                            "message": f"Imported {len(holdings)} metal holdings from Aura",
                            "transactions": len(holdings), "uncategorized": []}

            looks_cc = any(m in text2 for m in CC_TEXT_MARKERS)
            if kind == "cc" or (kind is None and looks_cc):
                result, k = P.detect_and_parse_cc(content), "cc"
                if not result["txns"] and kind is None:
                    alt = P.detect_and_parse_bank(content)
                    if alt["txns"]:
                        result, k = alt, "bank"
            else:
                result, k = P.detect_and_parse_bank(content), "bank"
                if not result["txns"] and kind is None:
                    alt = P.detect_and_parse_cc(content)
                    if alt["txns"]:
                        result, k = alt, "cc"
            if not result["txns"]:
                raise HTTPException(400, "No transactions found in this PDF "
                                         f"(tried bank and card parsers; best guess: {result.get('bank', '?')})")

            if k == "cc":
                card, created = _resolve_card(result, db, target_id)
                out = apply_cc_import(result, card, db)
                out.update({"kind": "cc", "target": f"{card.name}", "created_target": created})
                return out
            acc, created = _resolve_bank(result, db, target_id)
            out = apply_bank_import(result, acc, db)
            out.update({"kind": "bank", "target": f"{acc.name}", "created_target": created})
            return out

        # ── Excel / CSV ──
        content = decrypt_xlsx_if_needed(raw, password)
        rows = None
        try:
            rows = load_workbook_rows(content)
        except HTTPException:
            rows = None   # probably CSV — bank CSV handled below

        if rows and kind in (None, "investments"):
            broker = INV.detect_broker(rows)
            if broker:
                out = INV.run_broker_import(broker, rows, db)
                out.update({"kind": "investments", "target": broker, "created_target": False,
                            "transactions": out.get("imported", 0), "uncategorized": []})
                return out

        header_txt = " ".join(str(c).lower() for row in (rows or [])[:12] for c in (row or []) if c)
        k = kind or ("bank" if any(w in header_txt for w in ("withdrawal", "deposit", "debit", "credit", "balance"))
                     or not rows else "cc")

        if k == "bank":
            acc = (db.query(BankAccount).filter(BankAccount.id == target_id).first() if target_id else None) \
                  or _pick_by_filename(db.query(BankAccount).all(), fname, db, "bank")
            if rows:
                txn_data = BA._parse_statement_xlsx(content, acc.id)
            else:
                txn_data = BA._parse_statement_csv(content, acc.id)
            if not txn_data:
                raise HTTPException(400, "No transactions found in this statement file.")
            for t in txn_data:
                t.pop("account_id", None)
            latest_bal, latest_dt = 0.0, None
            for t in txn_data:
                if t["balance"] > 0 and (latest_dt is None or t["transaction_date"] > latest_dt):
                    latest_dt, latest_bal = t["transaction_date"], t["balance"]
            out = apply_bank_import({"txns": txn_data, "closing": latest_bal,
                                     "bank": "Excel/CSV statement"}, acc, db)
            out.update({"kind": "bank", "target": acc.name, "created_target": False})
            return out

        card = (db.query(CreditCard).filter(CreditCard.id == target_id).first() if target_id else None) \
               or _pick_by_filename(db.query(CreditCard).all(), fname, db, "cc")
        if rows:
            txn_data = CCR._parse_xlsx_statement(content, card.id)
        else:
            txn_data = CCR._parse_csv_statement(content, card.id)
        if not txn_data:
            raise HTTPException(400, "No transactions found in this statement file.")
        for t in txn_data:
            t.pop("card_id", None)
            t.setdefault("transaction_type", "debit")
        out = apply_cc_import({"txns": txn_data, "bank": "Excel/CSV statement"}, card, db)
        out.update({"kind": "cc", "target": card.name, "created_target": False})
        return out

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(400, f"Auto-import failed: {e}\n{traceback.format_exc()[-200:]}")
