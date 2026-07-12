"""
WealthOS PDF Parser — v7 (production rewrite)

ROOT CAUSE FIXES vs v6:
────────────────────────────────────────────────────────────────────────────

1. HDFC — complete rewrite of both summary + transaction extraction
   PROBLEM: v6 relied on extract_tables() with a 42% right-crop.
            The transaction table wasn't being detected by pdfplumber's
            table-finder because HDFC uses a custom drawn table (no PDF
            table borders). extract_tables() returned 0 transaction rows.
            Summary regex assumed label+value on the same line, but HDFC
            puts the total-due value on the NEXT line ("_ C12,764.00").
   FIX: Pure text-line parsing for both summary and transactions.
        Summary uses context-aware regex scanning subsequent lines.
        Transactions use a tight regex: dd/mm/yyyy| HH:MM  desc  [+] C amount
        Credit direction = presence of '+' before amount OR keywords
        (cashback, payment received, refund, reversal, adj).

2. AXIS — transaction description and column index bug
   PROBLEM: v6 used desc = cell(row, 1) but Axis table layout is:
            col 0=DATE, col 1=None (span artifact), col 2=DESCRIPTION,
            col 7=MERCHANT CATEGORY, col 8=AMOUNT.
            Result: every transaction had an empty description.
            Summary regex assumed label+value on same line; they're not.
   FIX: For transactions — use text-based line regex (cleanest, most robust).
        For summary — context-aware multi-line extraction.
        Dr/Cr suffix correctly maps to debit/credit.

3. CSB/JUPITER — transaction table is a single merged cell blob
   PROBLEM: The Jupiter PDF renderer places ALL transaction rows inside a
            single merged table cell. extract_tables() returns one giant
            string blob. The existing row-iterator found nothing because
            is_date_dmy_mon() never matched a cell key.
   FIX: Pure text-line parsing for both summary and transactions.
        Summary has clean paired lines (label then value on same line).
        Transactions: "DD Mon YYYY  DESCRIPTION  Rs. AMOUNT" per line.

4. Safe-float — unchanged from v6, works correctly.
   Handles: Rs.12,764.00 | C1,506.00 | Rs. 250.00 | 21,389.52 Dr | 890.90

Detection logic: text keyword scan on first 2 pages.
  HDFC   → "hdfc bank" or "hdfcbank"
  Axis   → "axis bank"
  CSB    → "csb bank" or ("jupiter" + "edge")
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import sys, os, io, re
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import BankAccount, CreditCard, CreditCardTransaction, Investment
from file_utils import decrypt_pdf_if_needed
from categorizer import load_rules, apply_rules, uncategorized_descriptions
from matching import apply_bank_import, apply_cc_import
from routers.bank_accounts import BankTransaction, guess_category

from routers.auth import require_auth

router = APIRouter(prefix="/pdf-import", tags=["pdf_import"], dependencies=[Depends(require_auth)])


# ── CORE UTILITIES ─────────────────────────────────────────────────────────────

def safe_float(s) -> float:
    """
    Parse Indian/US currency strings safely.
    '1,08,065.05' -> 108065.05  (strip commas only, KEEP decimal)
    'Rs. 250.00'  -> 250.0
    'C 1,506.00'  -> 1506.0     (HDFC uses 'C' as Rs symbol)
    '3,000.00 Dr' -> 3000.0
    '$1,149.59'   -> 1149.59
    '890.90'      -> 890.90     (NOT 89090 — never strip decimal point!)

    CRITICAL: Never use a character class that includes '.' — it will silently
    strip decimal points from numbers and produce 100x wrong values.
    Strip currency PREFIXES only (from the start of the string).
    """
    if not s:
        return 0.0
    cleaned = str(s).strip()
    # 1. Remove Dr/Cr accounting suffixes (must go first to avoid stripping digits)
    cleaned = re.sub(r'\s*(Dr|Cr|DR|CR)\s*$', '', cleaned).strip()
    # 2. Remove currency prefixes: "Rs.", "Rs ", "₹", "$", "C " (HDFC notation)
    #    Use anchored prefix removal — never remove '.' from the middle of a number
    cleaned = re.sub(r'^Rs\.?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^[₹\$]\s*', '', cleaned)
    cleaned = re.sub(r'^C\s+', '', cleaned)     # "C 1,506.00" -> "1,506.00"
    cleaned = re.sub(r'^C(?=\d)', '', cleaned)  # "C12,764.00" -> "12,764.00"
    # 3. Strip thousands-separator commas (NOT the decimal point)
    cleaned = cleaned.replace(',', '').strip()
    try:
        return float(cleaned)
    except Exception:
        return 0.0


def parse_date_str(s: str) -> datetime:
    if not s:
        return datetime.utcnow()
    s = str(s).strip().replace(',', '')
    for fmt in [
        "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y",
        "%d/%m/%y", "%d-%b-%y", "%m/%d/%Y", "%d %B %Y",
        "%b %d %Y",
    ]:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return datetime.utcnow()


def parse_date_obj(s: str) -> date:
    dt = parse_date_str(s)
    return dt.date() if dt else None


def get_pdf_pages(content: bytes):
    import pdfplumber
    return pdfplumber.open(io.BytesIO(content))


def cell(row, idx, default=""):
    try:
        v = row[idx]
        return str(v).strip() if v is not None else default
    except (IndexError, TypeError):
        return default


def is_date_dmy_mon(s: str) -> bool:
    return bool(re.match(r'\d{1,2}[\s\-]\w{3}[\s\-]\d{4}', str(s).strip()))


def pdf_full_text(content: bytes, max_pages: int = 999) -> str:
    with get_pdf_pages(content) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages[:max_pages])


# ── BANK STATEMENT PARSERS ─────────────────────────────────────────────────────

def parse_dbs(content: bytes) -> dict:
    """DBS DigiSavings. Table: Txn Date|Value Date|Details|Debit|Credit|Balance"""
    import pdfplumber
    txns = []
    closing = opening = 0.0

    with get_pdf_pages(content) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        m = re.search(r'Opening Balance\s+([\d,]+\.\d+)', full_text)
        if m: opening = safe_float(m.group(1))
        m = re.search(r'Closing Balance\s+([\d,]+\.\d+)', full_text)
        if m: closing = safe_float(m.group(1))

        prev_bal = opening
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or not row[0]: continue
                    date_str = cell(row, 0)
                    if not is_date_dmy_mon(date_str): continue
                    desc = cell(row, 2)
                    col3 = safe_float(cell(row, 3))
                    col4 = safe_float(cell(row, 4))
                    col5 = safe_float(cell(row, 5))
                    if col5 > 0:
                        bal, debit, credit = col5, col3, col4
                    elif col4 > 0 and col3 > 0:
                        bal = col4
                        credit, debit = (col3, 0.0) if col4 > prev_bal else (0.0, col3)
                    else:
                        continue
                    if debit == 0 and credit == 0:
                        amt = col3 or col4
                        credit, debit = (amt, 0.0) if bal > prev_bal else (0.0, amt)
                    closing = bal; prev_bal = bal
                    txns.append({
                        "transaction_date": parse_date_str(date_str),
                        "description": desc[:200], "debit_amount": debit,
                        "credit_amount": credit, "balance": bal,
                        "category": guess_category(desc), "reference": "",
                    })
    return {"txns": txns, "closing": closing, "opening": opening, "bank": "DBS DigiSavings"}


def parse_federal(content: bytes) -> dict:
    """Federal Bank (Jupiter). Cols: Date|ValueDate|Particulars|TranType|Cheque|Wd|Dep|Bal|DrCr"""
    import pdfplumber
    txns = []; closing = 0.0
    with get_pdf_pages(content) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or not row[0]: continue
                    date_str = cell(row, 0)
                    if not re.match(r'\d{2}/\d{2}/\d{4}', date_str): continue
                    desc = cell(row, 2)
                    if 'opening' in desc.lower(): continue
                    wd  = safe_float(cell(row, 5))
                    dep = safe_float(cell(row, 6))
                    bal = safe_float(cell(row, 7))
                    dr_cr = cell(row, 8).strip()
                    if wd == 0 and dep == 0:
                        amt = safe_float(cell(row, 5)) or safe_float(cell(row, 6))
                        wd, dep = (amt, 0.0) if dr_cr == 'Dr' else (0.0, amt)
                    closing = bal
                    txns.append({
                        "transaction_date": parse_date_str(date_str),
                        "description": desc[:200], "debit_amount": wd,
                        "credit_amount": dep, "balance": bal,
                        "category": guess_category(desc), "reference": cell(row, 4),
                    })
    return {"txns": txns, "closing": closing, "bank": "Federal Bank (Jupiter)"}


def parse_equitas(content: bytes) -> dict:
    """Equitas SFB. Cols: Date|Reference|Narration|Withdrawal|Deposit|Balance"""
    import pdfplumber
    txns = []; closing = 0.0
    with get_pdf_pages(content) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or not row[0]: continue
                    date_str = cell(row, 0)
                    if not is_date_dmy_mon(date_str): continue
                    ref = cell(row, 1); desc = cell(row, 2)
                    wd  = safe_float(cell(row, 3))
                    dep = safe_float(cell(row, 4))
                    bal = safe_float(cell(row, 5))
                    closing = bal
                    txns.append({
                        "transaction_date": parse_date_str(date_str),
                        "description": desc[:200], "debit_amount": wd,
                        "credit_amount": dep, "balance": bal,
                        "category": guess_category(desc), "reference": ref,
                    })
    return {"txns": txns, "closing": closing, "bank": "Equitas SFB"}


def parse_canara(content: bytes) -> dict:
    """Canara Bank. Cols: Date|Particulars|Deposits|Withdrawals|Balance"""
    import pdfplumber
    txns = []; closing = 0.0
    with get_pdf_pages(content) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or not row[0]: continue
                    date_str = cell(row, 0)
                    if not re.match(r'\d{2}[-/]\d{2}[-/]\d{4}', date_str): continue
                    desc = cell(row, 1)
                    dep = safe_float(cell(row, 2))
                    wd  = safe_float(cell(row, 3))
                    bal = safe_float(cell(row, 4))
                    closing = bal
                    txns.append({
                        "transaction_date": parse_date_str(date_str),
                        "description": desc[:200], "debit_amount": wd,
                        "credit_amount": dep, "balance": bal,
                        "category": guess_category(desc), "reference": "",
                    })
    return {"txns": txns, "closing": closing, "bank": "Canara Bank"}


def parse_generic_bank(content: bytes) -> dict:
    """
    Format-agnostic fallback: scan raw text lines for
      DATE  DESCRIPTION  AMOUNT  BALANCE [Dr|Cr]
    Debit/credit direction comes from (in priority order) the Dr/Cr marker,
    the running-balance delta, or credit-keyword hints in the description.
    Used only when every bank-specific parser produced zero transactions.
    """
    GENERIC_TXN = re.compile(
        r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[\s-][A-Za-z]{3,9}[\s-]\d{2,4})'  # date
        r'\s+(.*?)\s+'                                                             # description
        r'(-?[\d,]+\.\d{2})\s+'                                                    # amount
        r'(-?[\d,]+\.\d{2})'                                                       # closing balance
        r'\s*(Dr|Cr)?\s*$', re.IGNORECASE)
    CREDIT_HINTS = ('salary', 'neft cr', 'imps cr', 'received', 'refund',
                    'cashback', 'interest', 'credited', 'deposit', 'reversal')

    txns = []
    closing = 0.0
    prev_bal = None
    full_text = pdf_full_text(content)
    m = re.search(r'Opening Balance[^\d]*([\d,]+\.\d{2})', full_text, re.IGNORECASE)
    if m:
        prev_bal = safe_float(m.group(1))

    for line in full_text.split('\n'):
        m = GENERIC_TXN.match(line.strip())
        if not m:
            continue
        date_str, desc, amt_raw, bal_raw, dr_cr = m.groups()
        amount = abs(safe_float(amt_raw))
        balance = safe_float(bal_raw)
        if amount == 0:
            continue
        if dr_cr:
            is_credit = dr_cr.lower() == 'cr'
        elif prev_bal is not None:
            is_credit = balance > prev_bal
        else:
            is_credit = any(k in desc.lower() for k in CREDIT_HINTS)
        prev_bal = balance
        closing = balance
        txns.append({
            "transaction_date": parse_date_str(date_str),
            "description": desc[:200],
            "debit_amount": 0.0 if is_credit else amount,
            "credit_amount": amount if is_credit else 0.0,
            "balance": balance,
            "category": guess_category(desc),
            "reference": "",
        })
    return {"txns": txns, "closing": closing, "bank": "Bank statement (generic parser)"}


BANK_PARSERS = [
    (("digibank", "dbss0in", "dbs bank"), parse_dbs),
    (("federal bank", "fdrl0007777"), parse_federal),
    (("equitas", "esfb000"), parse_equitas),
    (("canara", "cnrb000", "syndicate"), parse_canara),
]


def detect_and_parse_bank(content: bytes) -> dict:
    """
    Evidence-based detection instead of blind keyword routing:
    1. Run the parser whose keywords match — trust it only if it finds rows.
    2. Otherwise run every bank parser and keep the one extracting the most
       transactions (a wrong-keyword match can no longer return silent zeros).
    3. Final fallback: the generic text-line parser.
    """
    with get_pdf_pages(content) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages[:2]).lower()

    detected = next((fn for kws, fn in BANK_PARSERS if any(k in text for k in kws)), None)
    if detected:
        try:
            result = detected(content)
            if result["txns"]:
                return result
        except Exception:
            pass

    best = None
    for _, fn in BANK_PARSERS:
        if fn is detected:
            continue
        try:
            r = fn(content)
        except Exception:
            continue
        if best is None or len(r["txns"]) > len(best["txns"]):
            best = r
    if best and best["txns"]:
        best["bank"] += " (auto-detected)"
        return best

    generic = parse_generic_bank(content)
    if generic["txns"]:
        return generic
    return generic


# ── CREDIT CARD PARSERS ────────────────────────────────────────────────────────

def _empty_cc_summary() -> dict:
    return {
        "total_due": 0.0, "min_due": 0.0, "credit_limit": 0.0,
        "available_credit": 0.0, "available_cash_limit": 0.0,
        "payment_due_date": None, "statement_date": None,
        "billing_start": None, "billing_end": None, "card_number": "",
    }


def parse_hdfc_cc(content: bytes) -> dict:
    """
    HDFC Credit Card — text-line parser (no extract_tables).

    HDFC uses visually-drawn table borders (not PDF table primitives).
    pdfplumber.extract_tables() finds zero transaction rows. The raw
    extract_text() output is clean and fully parseable with regex.

    SUMMARY (page 1):
      Line N:   "... TOTAL AMOUNT DUE"           <- label
      Line N+1: "_ C12,764.00"                   <- value
      Line M+1: "C640.00 07 Mar, 2026"           <- min_due + due_date
      Line M+2: "C90,000 C76,882 C36,000"        <- limits
      Inline:   "Billing Period 16 Jan - 15 Feb"

    TRANSACTIONS:
      "16/01/2026| 00:00 BLINKITGURGAON C 1,506.00 l"    <- debit
      "16/01/2026| 00:00 10% Swiggy Cashback + C 890.90 l" <- credit
    """
    txns = []; summary = _empty_cc_summary()

    with get_pdf_pages(content) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            lines = text.split('\n')

            for i, line in enumerate(lines):
                ls = line.strip()

                if not summary["total_due"]:
                    m = re.match(r'^[_\s]*C\s*([\d,]+\.?\d*)\s*$', ls)
                    if m:
                        prev = lines[i-1].strip() if i > 0 else ""
                        if 'TOTAL AMOUNT DUE' in prev or page_idx == 0:
                            summary["total_due"] = safe_float(m.group(1))

                if not summary["min_due"]:
                    m = re.match(r'^C\s*([\d,]+\.?\d*)\s+(\d{2}\s+\w+,?\s+\d{4})\s*$', ls)
                    if m:
                        summary["min_due"] = safe_float(m.group(1))
                        summary["payment_due_date"] = parse_date_obj(m.group(2))

                if not summary["credit_limit"]:
                    m = re.match(r'^C\s*([\d,]+)\s+C\s*([\d,]+\.?\d*)\s+C\s*([\d,]+)\s*$', ls)
                    if m:
                        summary["credit_limit"]         = safe_float(m.group(1))
                        summary["available_credit"]     = safe_float(m.group(2))
                        summary["available_cash_limit"] = safe_float(m.group(3))

                if not summary["billing_start"]:
                    m = re.search(
                        r'Billing Period\s+(\d{2}\s+\w+,?\s+\d{4})\s*[-]\s*(\d{2}\s+\w+,?\s+\d{4})',
                        ls, re.IGNORECASE)
                    if m:
                        summary["billing_start"] = parse_date_obj(m.group(1))
                        summary["billing_end"]   = parse_date_obj(m.group(2))

                if not summary["statement_date"]:
                    m = re.search(r'Statement Date\s+(\d{1,2}\s+\w+,?\s+\d{4})', ls, re.IGNORECASE)
                    if m: summary["statement_date"] = parse_date_obj(m.group(1))

                if not summary["card_number"]:
                    m = re.search(r'(\d{6}X{4,6}\d{4})', ls)
                    if m: summary["card_number"] = m.group(1)

            # Transactions: "dd/mm/yyyy| HH:MM  desc  [+] C amount [l]"
            TXN_RE = re.compile(
                r'^(\d{2}/\d{2}/\d{4})\|\s*\d{2}:\d{2}\s+(.+?)\s+(\+\s*)?C\s*([\d,]+\.?\d*)\s*(?:l\s*)?$',
                re.IGNORECASE)
            for line in lines:
                m = TXN_RE.match(line.strip())
                if not m: continue
                date_str, desc, plus_flag, amt_raw = m.groups()
                amt = safe_float(amt_raw)
                if amt == 0: continue
                is_credit = bool(plus_flag) or any(
                    kw in desc.lower() for kw in
                    ['cashback', 'payment', 'refund', 'reversal', 'adj', 'credit', 'waiver']
                )
                txns.append({
                    "transaction_date": parse_date_str(date_str),
                    "description": desc[:200], "amount": amt,
                    "transaction_type": "credit" if is_credit else "debit",
                    "category": guess_cc_cat(desc),
                })

    return {"txns": txns, **summary, "bank": "HDFC"}


def parse_axis_cc(content: bytes) -> dict:
    """
    Axis Bank Credit Card (MyZone Rupay / Neo) — text-line parser.

    v6 BUG: extract_tables() col 1 = None (span artifact), col 2 = description.
    v6 code used cell(row,1) for desc → all descriptions were empty.

    Text is perfectly structured — use that instead:
      Summary row:  "21,389.52 Dr 16,955.00 Dr 14/01/2026 - 12/02/2026 04/03/2026 ..."
      Limits row:   "653046******8148 70,000.00 36,327.48 21,000.00 ..."
      Transaction:  "14/01/2026 EMI INTEREST - 3/3, REF# 64785309 MISC STORE 138.55 Dr"
      Payment:      "01/02/2026 BBPS PAYMENT RECEIVED - ... 14,685.48 Cr"
    """
    txns = []; summary = _empty_cc_summary()

    with get_pdf_pages(content) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split('\n')

            for ls in (l.strip() for l in lines):
                # Summary data row: "amt Dr amt Dr period due_date stmt_date"
                if not summary["total_due"]:
                    m = re.match(
                        r'^([\d,]+\.\d{2})\s+Dr\s+([\d,]+\.\d{2})\s+Dr\s+'
                        r'(\d{2}/\d{2}/\d{4})\s*[-]\s*(\d{2}/\d{2}/\d{4})\s+'
                        r'(\d{2}/\d{2}/\d{4})', ls)
                    if m:
                        summary["total_due"]        = safe_float(m.group(1))
                        summary["min_due"]          = safe_float(m.group(2))
                        summary["billing_start"]    = parse_date_obj(m.group(3))
                        summary["billing_end"]      = parse_date_obj(m.group(4))
                        summary["payment_due_date"] = parse_date_obj(m.group(5))

                # Credit limits row: "cardnum credit_limit avail_credit avail_cash ..."
                if not summary["credit_limit"]:
                    m = re.match(
                        r'^\d{6}\*{6}\d{4}\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})',
                        ls)
                    if m:
                        summary["credit_limit"]         = safe_float(m.group(1))
                        summary["available_credit"]     = safe_float(m.group(2))
                        summary["available_cash_limit"] = safe_float(m.group(3))

                if not summary["card_number"]:
                    m = re.search(r'(\d{6}\*{6}\d{4})', ls)
                    if m: summary["card_number"] = m.group(1)

                if not summary["statement_date"]:
                    m = re.search(r'Statement (?:Generation )?Date\s+(\d{2}/\d{2}/\d{4})', ls, re.IGNORECASE)
                    if m: summary["statement_date"] = parse_date_obj(m.group(1))

            # Transactions: "dd/mm/yyyy DESCRIPTION [CATEGORY] amount Dr|Cr"
            TXN_RE = re.compile(
                r'^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+(Dr|Cr)\s*$',
                re.IGNORECASE)
            for line in lines:
                m = TXN_RE.match(line.strip())
                if not m: continue
                date_str, desc, amt_raw, dr_cr = m.groups()
                amt = safe_float(amt_raw)
                if amt == 0: continue
                txns.append({
                    "transaction_date": parse_date_str(date_str),
                    "description": desc[:200], "amount": amt,
                    "transaction_type": "credit" if dr_cr.capitalize() == "Cr" else "debit",
                    "category": guess_cc_cat(desc),
                })

    return {"txns": txns, **summary, "bank": "Axis"}


def parse_csb_cc(content: bytes) -> dict:
    """
    CSB Bank Edge Credit Card (Jupiter) — pymupdf block parser.

    PERFORMANCE FIX: pdfplumber extract_text() takes 4.5s on CSB PDFs due to
    complex vector graphics (1600-2200 curves/page). pymupdf processes the same
    PDFs in ~74ms (60x speedup).

    Block structure (pymupdf):
      Page 1 summary fields (values in separate blocks from labels):
        "Rs. 13,702.58\n01 Mar 2026"    — total_due + due_date
        "Rs. 500.00\n17/02/2026"         — min_due + stmt_date
        "Rs. 75,000\nRs. 61,297.42\n..."— credit_limit + available_credit
      Billing period: "17 JAN 2026 - 16 FEB 2026" (header block)
      Transactions (pages 2+): each txn is its own block:
        ["DD Mon YYYY", "HH:MM AM/PM", "DESCRIPTION", "Rs. AMOUNT"]
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        # Fallback to pdfplumber if pymupdf not installed
        return _parse_csb_cc_pdfplumber(content)

    doc = fitz.open(stream=content, filetype="pdf")
    txns = []
    summary = _empty_cc_summary()

    DATE_LINE = re.compile(r'^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})$')
    TIME_LINE = re.compile(r'^\d{1,2}:\d{2}\s*[AP]M$')

    for page_num, page in enumerate(doc):
        if page_num == 0:
            # Page 1: pymupdf outputs each value on its OWN line (labels and values separate)
            # e.g. "Rs. 13,702.58" on line N, "01 Mar 2026" on line N+1
            # Must match consecutive lines.
            full_p1 = page.get_text()
            lines_p1 = [l.strip() for l in full_p1.split('\n') if l.strip()]
            for i, ls in enumerate(lines_p1):
                nxt = lines_p1[i+1] if i+1 < len(lines_p1) else ""
                # total_due + payment_due_date: "Rs. X" / "DD Mon YYYY"
                if not summary["total_due"]:
                    m = re.match(r'^Rs\.\s*([\d,]+\.?\d*)$', ls)
                    m2 = re.match(r'^(\d{1,2}\s+\w+\s+\d{4})$', nxt)
                    if m and m2:
                        summary["total_due"]        = safe_float(m.group(1))
                        summary["payment_due_date"] = parse_date_obj(m2.group(1))
                # min_due + statement_date: "Rs. X" / "DD/MM/YYYY"
                if not summary["min_due"]:
                    m = re.match(r'^Rs\.\s*([\d,]+\.?\d*)$', ls)
                    m2 = re.match(r'^(\d{2}/\d{2}/\d{4})$', nxt)
                    if m and m2:
                        summary["min_due"]        = safe_float(m.group(1))
                        summary["statement_date"] = parse_date_obj(m2.group(1))
                # credit_limit + available_credit: "Rs. X" / "Rs. Y"
                if not summary["credit_limit"]:
                    m = re.match(r'^Rs\.\s*([\d,]+)$', ls)   # no .00 on credit limit
                    m2 = re.match(r'^Rs\.\s*([\d,]+\.?\d*)$', nxt)
                    if m and m2:
                        summary["credit_limit"]     = safe_float(m.group(1))
                        summary["available_credit"] = safe_float(m2.group(1))
                # billing period: "17 JAN 2026 - 16 FEB 2026" on single line
                if not summary["billing_start"]:
                    m = re.match(r'^(\d{1,2}\s+\w{3}\s+\d{4})\s*[-]\s*(\d{1,2}\s+\w{3}\s+\d{4})$',
                                 ls, re.IGNORECASE)
                    if m:
                        summary["billing_start"] = parse_date_obj(m.group(1))
                        summary["billing_end"]   = parse_date_obj(m.group(2))
                if not summary["card_number"]:
                    m = re.search(r'(XXXX\s*XXXX\s*XXXX\s*\d{4})', ls, re.IGNORECASE)
                    if m: summary["card_number"] = m.group(1)
            continue

        # Pages 2+: parse transaction blocks
        blocks = page.get_text("blocks")
        for block in blocks:
            raw = block[4].strip()
            if not raw: continue
            lines = [l.strip() for l in raw.split('\n') if l.strip()]
            if len(lines) < 3: continue

            # Block structure: DATE / TIME / DESC... / AMOUNT
            if not DATE_LINE.match(lines[0]): continue
            if not TIME_LINE.match(lines[1]): continue

            amt_m = re.search(r'Rs\.\s*([\d,]+\.?\d{0,2})', lines[-1])
            if not amt_m: continue

            amount   = safe_float(amt_m.group(1))
            if amount == 0: continue
            desc     = ' '.join(lines[2:-1]) if len(lines) > 3 else lines[2]
            try:
                txn_date = datetime.strptime(lines[0], '%d %b %Y').date()
            except Exception:
                continue

            is_payment = any(x in desc.lower() for x in
                             ['repayment', 'payment received', 'refund', 'reversal'])
            txns.append({
                "transaction_date": parse_date_str(lines[0]),
                "description": desc[:200], "amount": amount,
                "transaction_type": "payment" if is_payment else "debit",
                "category": guess_cc_cat(desc),
            })

    return {"txns": txns, **summary, "bank": "CSB (Jupiter)"}


def _parse_csb_cc_pdfplumber(content: bytes) -> dict:
    """Fallback CSB parser using pdfplumber (slower, ~4.5s on complex PDFs)."""
    txns = []; summary = _empty_cc_summary()
    with get_pdf_pages(content) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            lines = text.split('\n')
            if page_idx == 0:
                for ls in (l.strip() for l in lines):
                    if not summary["total_due"]:
                        m = re.match(r'^Rs\.\s*([\d,]+\.?\d*)\s+(\d{1,2}\s+\w+\s+\d{4})\s*$', ls)
                        if m:
                            summary["total_due"]        = safe_float(m.group(1))
                            summary["payment_due_date"] = parse_date_obj(m.group(2))
                    if not summary["min_due"]:
                        m = re.match(r'^Rs\.\s*([\d,]+\.?\d*)\s+(\d{2}/\d{2}/\d{4})\s*$', ls)
                        if m:
                            summary["min_due"] = safe_float(m.group(1))
                    if not summary["credit_limit"]:
                        m = re.match(r'^Rs\.\s*([\d,]+\.?\d*)\s+Rs\.\s*([\d,]+\.?\d*)\s*$', ls)
                        if m:
                            summary["credit_limit"]     = safe_float(m.group(1))
                            summary["available_credit"] = safe_float(m.group(2))
                    if not summary["billing_start"]:
                        m = re.match(
                            r'^(\d{1,2}\s+\w{3}\s+\d{4})\s*[-]\s*(\d{1,2}\s+\w{3}\s+\d{4})\s*$',
                            ls, re.IGNORECASE)
                        if m:
                            summary["billing_start"] = parse_date_obj(m.group(1))
                            summary["billing_end"]   = parse_date_obj(m.group(2))
                    if not summary["card_number"]:
                        m = re.search(r'(XXXX\s*XXXX\s*XXXX\s*\d{4})', ls, re.IGNORECASE)
                        if m: summary["card_number"] = m.group(1)
            TXN_RE = re.compile(
                r'^(\d{1,2}\s+\w{3}\s+\d{4})\s+(.+?)\s+Rs\.\s*([\d,]+\.?\d{0,2})\s*$',
                re.IGNORECASE)
            for line in lines:
                m = TXN_RE.match(line.strip())
                if not m: continue
                date_str, desc, amt_raw = m.groups()
                amt = safe_float(amt_raw)
                if amt == 0: continue
                is_payment = 'repayment' in desc.lower()
                txns.append({
                    "transaction_date": parse_date_str(date_str),
                    "description": desc[:200], "amount": amt,
                    "transaction_type": "payment" if is_payment else "debit",
                    "category": guess_cc_cat(desc),
                })
    return {"txns": txns, **summary, "bank": "CSB (Jupiter)"}


def guess_cc_cat(desc: str) -> str:
    d = desc.lower()
    # ── High-priority checks first (prevent merchant names from overriding) ──
    # 1. Cashback / refund — must precede food (e.g. "10% Swiggy Cashback" has 'swiggy')
    if any(x in d for x in ['cashback', 'refund', 'reversal', '%']):
        if any(x in d for x in ['cashback', 'refund', 'reversal', 'adj cb', 'ornge cb', 'blck cb']):
            return 'Cashback / Refund'
    # 2. Bill payment — must precede utilities (e.g. "BBPS PAYMENT RECEIVED" has 'bbps')
    if any(x in d for x in ['payment received', 'repayment', 'mb/ib payment', 'bppy cc payment']):
        return 'Bill Payment'
    # 3. Finance charges
    if any(x in d for x in ['emi interest', 'emi principal', 'gst on', 'finance charge',
                              'interest charge']):
        return 'Finance Charges'
    if d.strip() in ('gst',): return 'Finance Charges'  # bare "GST" line
    # ── Standard categories ──
    if any(x in d for x in [
        'blinkit', 'zepto', 'bigbasket', 'grocer', 'instamart',
        'dmart', 'supermarket', 'grocery', 'reliance fresh',
    ]): return 'Groceries'
    if any(x in d for x in [
        # Entertainment — before food/cafe check
        'netflix', 'prime video', 'hotstar', 'spotify', 'bookmyshow', 'book my show',
        'cinema', 'pvr', 'inox', 'vr mall', 'theatre', 'hivemind', 'ampa skyone',
    ]): return 'Entertainment'
    if any(x in d for x in [
        'swiggy', 'zomato', 'food', 'restaurant', 'cafe', 'mcdonald', 'kfc',
        'biryani', 'snacks', 'bakery', 'dining', 'pizza', 'burger', 'domino',
        'eat', 'kitchen', 'diner', 'sweet', 'mishwar', 'district dining', 'badmaash',
    ]): return 'Food & Dining'
    if any(x in d for x in [
        'amazon', 'flipkart', 'myntra', 'life style', 'lifestyle', 'shopping', 'mall',
        'ajio', 'meesho', 'nykaa', 'dept store', 'cyms', 'mas vr',
    ]): return 'Shopping'
    if any(x in d for x in [
        'redbus', 'irctc', 'railyatri', 'rapido', 'uber', 'ola', 'metro',
        'train', 'airline', 'flight', 'indigo', 'makemytrip', 'make my trip',
        'cab', 'taxi', 'ing*make',
    ]): return 'Travel'
    if any(x in d for x in [
        'airtel', 'jio', 'vodafone', 'bsnl', 'paytm', 'recharge',
        'electricity', 'internet', 'broadband', 'ptm*bharti',
    ]): return 'Utilities'
    if any(x in d for x in [
        'pharmacy', 'hospital', 'medical', 'clinic', 'health', 'medplus',
        'apollo', 'fortis', '1mg', 'netmeds', 'pharmeasy',
    ]): return 'Healthcare'
    if any(x in d for x in ['petrol', 'fuel', 'diesel', 'hpcl', 'iocl', 'bpcl']):
        return 'Fuel'
    if any(x in d for x in ['cashback', 'refund', 'reversal', 'adj']):
        return 'Cashback / Refund'
    if any(x in d for x in ['payment', 'repayment', 'bbps']):
        return 'Bill Payment'
    if any(x in d for x in ['emi', 'gst']): return 'Finance Charges'
    return 'Other'


def parse_generic_cc(content: bytes) -> dict:
    """
    Format-agnostic CC fallback: scan text lines for
      DATE  DESCRIPTION  [Rs./₹/C] AMOUNT [Dr|Cr]
    Credit direction from the Cr marker or payment/cashback keywords.
    Summary fields stay empty — transactions still import.
    """
    GENERIC_TXN = re.compile(
        r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[\s-][A-Za-z]{3,9}[\s-]\d{4})'
        r'\s+(.+?)\s+'
        r'(?:Rs\.?\s*|₹\s*|C\s*)?(-?[\d,]+\.\d{2})\s*(Dr|Cr)?\s*$', re.IGNORECASE)
    CREDIT_HINTS = ('payment', 'repayment', 'cashback', 'refund', 'reversal', 'waiver', 'credit')

    txns = []
    summary = _empty_cc_summary()
    for line in pdf_full_text(content).split('\n'):
        m = GENERIC_TXN.match(line.strip())
        if not m:
            continue
        date_str, desc, amt_raw, dr_cr = m.groups()
        amount = abs(safe_float(amt_raw))
        if amount == 0:
            continue
        is_credit = (dr_cr or '').lower() == 'cr' or any(k in desc.lower() for k in CREDIT_HINTS)
        txns.append({
            "transaction_date": parse_date_str(date_str),
            "description": desc[:200], "amount": amount,
            "transaction_type": "credit" if is_credit else "debit",
            "category": guess_cc_cat(desc),
        })
    return {"txns": txns, **summary, "bank": "Credit card (generic parser)"}


CC_PARSERS = [
    (("hdfc bank", "hdfcbank"), parse_hdfc_cc),
    (("axis bank",), parse_axis_cc),
    (("csb bank",), parse_csb_cc),
]


def detect_and_parse_cc(content: bytes) -> dict:
    """Same evidence-based strategy as detect_and_parse_bank: keyword match
    first, but only trusted when it yields transactions; then best-of-all
    parsers; then the generic text-line fallback."""
    with get_pdf_pages(content) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages[:2]).lower()

    detected = next((fn for kws, fn in CC_PARSERS if any(k in text for k in kws)), None)
    if detected is None and 'jupiter' in text and 'edge' in text:
        detected = parse_csb_cc
    if detected:
        try:
            result = detected(content)
            if result["txns"]:
                return result
        except Exception:
            pass

    best = None
    for _, fn in CC_PARSERS:
        if fn is detected:
            continue
        try:
            r = fn(content)
        except Exception:
            continue
        if best is None or len(r["txns"]) > len(best["txns"]):
            best = r
    if best and best["txns"]:
        best["bank"] += " (auto-detected)"
        return best

    return parse_generic_cc(content)


# ── INVESTMENT PARSERS ─────────────────────────────────────────────────────────

def get_usd_inr_rate() -> float:
    try:
        import urllib.request, json as _json
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        return 84.0


def parse_alpaca(content: bytes) -> list:
    holdings = []; usd_inr = get_usd_inr_rate()
    full_text = pdf_full_text(content)
    pattern = re.compile(
        r'^([A-Z]{1,5})\s+(.+?)\s+([\d.]+)\s+\$([\d,]+\.\d+)\s+\$([\d,]+\.\d+)\s+\$([\d,]+\.\d+)',
        re.MULTILINE)
    for m in pattern.finditer(full_text):
        sym, desc, qty, price_usd, mkt_val_usd, cost_usd = m.groups()
        if sym in ('USD', 'FDIC', 'SEC'): continue
        mkt_val = safe_float(mkt_val_usd); cost = safe_float(cost_usd)
        holdings.append({
            "name": desc.strip()[:100], "asset_class": "us_stocks", "platform": "Alpaca",
            "invested_amount": round(cost * usd_inr, 2), "current_value": round(mkt_val * usd_inr, 2),
            "units": float(qty), "symbol": sym, "currency": "USD", "fx_rate": usd_inr,
            "notes": f"Qty:{qty} @ ${price_usd} | USD/INR:{usd_inr:.2f} | Cost:${cost_usd} | MktVal:${mkt_val_usd}",
        })
    return holdings


def parse_aura(content: bytes) -> list:
    holdings = []; full_text = pdf_full_text(content)
    for metal, sym, cls in [('Gold', 'GOLD', 'digital_gold'), ('Silver', 'SILVER', 'digital_silver')]:
        m = re.search(rf'{metal}\s+([\d.]+)\s*gm', full_text, re.IGNORECASE)
        if m and float(m.group(1)) > 0:
            qty = float(m.group(1))
            holdings.append({
                "name": f"Aura Digital {metal}", "asset_class": cls, "platform": "Aura",
                "invested_amount": 0.0, "current_value": 0.0, "units": qty,
                "symbol": sym, "currency": "INR", "fx_rate": 0.0,
                "notes": f"{qty}gm digital {metal.lower()} via Aura — refresh price to update value",
            })
    return holdings


# ── ENDPOINTS ──────────────────────────────────────────────────────────────────

@router.post("/bank/{acc_id}")
async def import_bank_pdf(acc_id: int, file: UploadFile = File(...),
                          password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    acc = db.query(BankAccount).filter(BankAccount.id == acc_id).first()
    if not acc:
        raise HTTPException(404, "Account not found")
    content = await file.read()
    content = decrypt_pdf_if_needed(content, password)
    try:
        result = detect_and_parse_bank(content)
        if not result["txns"]:
            raise HTTPException(400, f"No transactions found. Detected format: {result['bank']}")
        return apply_bank_import(result, acc, db)
    except HTTPException: raise
    except Exception as e:
        import traceback
        raise HTTPException(400, f"PDF parse error: {e}\n{traceback.format_exc()[-300:]}")


@router.post("/credit-card/{card_id}")
async def import_cc_pdf(card_id: int, file: UploadFile = File(...),
                        password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    content = await file.read()
    content = decrypt_pdf_if_needed(content, password)
    try:
        result = detect_and_parse_cc(content)
        return apply_cc_import(result, card, db)
    except HTTPException: raise
    except Exception as e:
        import traceback
        raise HTTPException(400, f"PDF parse error: {e}\n{traceback.format_exc()[-300:]}")


@router.post("/investments/alpaca")
async def import_alpaca_pdf(file: UploadFile = File(...),
                            password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    content = await file.read()
    content = decrypt_pdf_if_needed(content, password)
    try:
        holdings = parse_alpaca(content)
        if not holdings:
            raise HTTPException(400, "No US stock holdings found. Check this is an Alpaca monthly statement PDF.")
        db.query(Investment).filter(Investment.platform == "Alpaca").delete()
        for h in holdings: db.add(Investment(**h))
        db.commit()
        fx = holdings[0]["fx_rate"] if holdings else 84.0
        return {"message": f"Imported {len(holdings)} US stocks from Alpaca (USD/INR: {fx:.2f})", "imported": len(holdings), "fx_rate": fx}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400, f"PDF parse error: {e}")


@router.post("/investments/aura")
async def import_aura_pdf(file: UploadFile = File(...),
                          password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    content = await file.read()
    content = decrypt_pdf_if_needed(content, password)
    try:
        holdings = parse_aura(content)
        if not holdings:
            raise HTTPException(400, "No gold/silver holdings found in this PDF.")
        db.query(Investment).filter(Investment.platform == "Aura").delete()
        for h in holdings: db.add(Investment(**h))
        db.commit()
        return {"message": f"Imported {len(holdings)} metal holdings from Aura", "imported": len(holdings), "details": [f"{h['name']}: {h['units']}gm" for h in holdings]}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400, f"PDF parse error: {e}")


@router.post("/credit-card-preview")
async def preview_cc_pdf(file: UploadFile = File(...),
                         password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """Parse CC PDF, return structured data without saving. Used by 'Add from Statement' flow."""
    content = await file.read()
    content = decrypt_pdf_if_needed(content, password)
    try:
        result = detect_and_parse_cc(content)
        rules = load_rules(db)
        for t in result["txns"]:
            t["category"] = apply_rules(t["description"], t["category"], rules)
        txns_preview = result["txns"][:10]
        return {
            "bank": result.get("bank", ""), "card_number": result.get("card_number", ""),
            "credit_limit": result.get("credit_limit", 0), "available_credit": result.get("available_credit", 0),
            "available_cash_limit": result.get("available_cash_limit", 0), "total_due": result.get("total_due", 0),
            "minimum_due": result.get("min_due", 0), "payment_due_date": str(result.get("payment_due_date") or ""),
            "statement_date": str(result.get("statement_date") or ""), "billing_start": str(result.get("billing_start") or ""),
            "billing_end": str(result.get("billing_end") or ""), "transaction_count": len(result["txns"]),
            "transactions_preview": [
                {"date": t["transaction_date"].strftime("%d %b"), "description": t["description"][:60],
                 "amount": t["amount"], "category": t["category"], "type": t["transaction_type"]}
                for t in txns_preview
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(400, f"Could not parse PDF: {e}\n{traceback.format_exc()[-300:]}")
