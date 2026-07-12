from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import sys, os, io, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from file_utils import decrypt_xlsx_if_needed, load_workbook_rows
from models import Investment
from schemas import InvestmentCreate, InvestmentUpdate

from routers.auth import require_auth

router = APIRouter(prefix="/investments", tags=["investments"], dependencies=[Depends(require_auth)])


def enrich(inv: Investment) -> dict:
    cv = inv.current_value or 0
    ia = inv.invested_amount or 0
    pnl = cv - ia
    pnl_pct = (pnl / ia * 100) if ia > 0 else 0
    return {
        "id": inv.id, "name": inv.name, "asset_class": inv.asset_class,
        "platform": inv.platform, "invested_amount": inv.invested_amount,
        "current_value": inv.current_value, "units": inv.units,
        "symbol": inv.symbol, "notes": inv.notes,
        "last_updated": inv.last_updated, "created_at": inv.created_at,
        "pnl": round(pnl, 2), "pnl_percent": round(pnl_pct, 2),
    }


def safe_float(val):
    if val is None: return 0.0
    try: return float(str(val).replace(",", "").replace("₹", "").replace("$", "").strip() or 0)
    except: return 0.0


def fetch_usd_inr() -> float:
    """USD→INR rate from Yahoo; falls back to a recent static rate offline."""
    try:
        import urllib.request, json as _json
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        return 84.0


def fetch_live_price(symbol: str) -> Optional[float]:
    """Fetch live price from Yahoo Finance (no API key needed)"""
    try:
        import urllib.request, json as _json
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            return float(price)
    except Exception:
        return None


# ISIN → Yahoo Finance symbol map for NSE stocks
ISIN_TO_YAHOO = {
    "INF457M01133": "CPSEETF.NS",
    "INE041025011": "EMBASSY.NS",
    "INE063P01018": "EQUITASBNK.NS",
    "INF109KC1Y56": "SILVERIETF.NS",
    "INE0NDH25011": "NEXUSSELECT.NS",
    "INF204KA1MS3": "DIVIDENDOPP.NS",
    "INF732E01045": "JUNIORBEES.NS",
    "INF732E01037": "LIQUIDBEES.NS",
    "INF204KB14I2": "NIFTYBEES.NS",
    "INF0R8F01042": "GOLDCASE.NS",
    "INF0R8F01034": "LIQUIDCASE.NS",
}


@router.get("/", response_model=List[dict])
def get_investments(asset_class: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Investment)
    if asset_class:
        q = q.filter(Investment.asset_class == asset_class)
    return [enrich(i) for i in q.all()]


@router.post("/", response_model=dict)
def create_investment(data: InvestmentCreate, db: Session = Depends(get_db)):
    inv = Investment(**data.model_dump())
    db.add(inv); db.commit(); db.refresh(inv)
    return enrich(inv)


@router.put("/{inv_id}", response_model=dict)
def update_investment(inv_id: int, data: InvestmentUpdate, db: Session = Depends(get_db)):
    inv = db.query(Investment).filter(Investment.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(inv, k, v)
    inv.last_updated = datetime.utcnow()
    db.commit(); db.refresh(inv)
    return enrich(inv)


@router.delete("/{inv_id}")
def delete_investment(inv_id: int, db: Session = Depends(get_db)):
    inv = db.query(Investment).filter(Investment.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(inv); db.commit()
    return {"message": "Deleted"}


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    investments = db.query(Investment).all()
    total_invested = sum((i.invested_amount or 0) for i in investments)
    total_current  = sum((i.current_value  or 0) for i in investments)
    total_pnl = total_current - total_invested
    pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    by_class = {}
    for inv in investments:
        ac = inv.asset_class
        if ac not in by_class:
            by_class[ac] = {"invested": 0, "current": 0, "count": 0}
        by_class[ac]["invested"] += (inv.invested_amount or 0)
        by_class[ac]["current"]  += (inv.current_value  or 0)
        by_class[ac]["count"] += 1
    allocation = [
        {"asset_class": ac, "invested": round(v["invested"], 2), "current": round(v["current"], 2),
         "pnl": round(v["current"] - v["invested"], 2),
         "percent": round(v["current"] / total_current * 100, 2) if total_current > 0 else 0,
         "count": v["count"]}
        for ac, v in by_class.items()
    ]
    return {"total_invested": round(total_invested, 2), "total_current": round(total_current, 2),
            "total_pnl": round(total_pnl, 2), "pnl_percent": round(pnl_pct, 2), "allocation": allocation}


@router.post("/refresh-prices")
def refresh_prices(db: Session = Depends(get_db)):
    """Update current values using Yahoo Finance live prices.
    FIX: US stocks (currency=USD) have USD prices → must multiply by USD/INR rate.
         All other stocks are INR-priced — store directly.
    """
    investments = db.query(Investment).all()
    updated, failed = [], []

    # Fetch USD/INR once if any US stocks need it
    has_usd = any(getattr(inv, 'currency', 'INR') == 'USD' for inv in investments if inv.symbol)
    usd_inr = fetch_usd_inr() if has_usd else None

    for inv in investments:
        if not inv.symbol:
            failed.append({"name": inv.name, "reason": "no symbol set"})
            continue
        price = fetch_live_price(inv.symbol)
        if price and inv.units > 0:
            currency = getattr(inv, 'currency', 'INR') or 'INR'
            if currency == 'USD' and usd_inr:
                # Price from Yahoo is in USD for US tickers → convert to INR
                price_inr = price * usd_inr
                inv.current_value = round(price_inr * inv.units, 2)
                inv.fx_rate = usd_inr
            else:
                inv.current_value = round(price * inv.units, 2)
            inv.last_updated = datetime.utcnow()
            db.commit()
            updated.append({"name": inv.name, "price_native": price, "currency": currency,
                             "value_inr": inv.current_value})
        else:
            failed.append({"name": inv.name, "reason": "price fetch failed or no units"})
    return {"updated": len(updated), "failed": len(failed), "usd_inr": usd_inr,
            "details_updated": updated, "details_failed": failed}


def detect_broker(rows) -> Optional[str]:
    """Guess which broker exported this workbook (used by auto-import)."""
    txt = " ".join(str(c).lower() for row in rows[:15] for c in (row or []) if c)
    if "scheme name" in txt or "folio" in txt:
        return "groww_mf"
    if "stock name" in txt or "scrip name" in txt:
        return "groww_stocks"
    if "stock symbol" in txt or "alpaca" in txt or "indmoney" in txt or "holdings_book" in txt:
        return "indmoney"
    if "coin" in txt:
        return "coinswitch"
    return None


def run_broker_import(broker: str, rows: list, db: Session) -> dict:
    imported = 0
    skipped = 0

    # ── Groww Stocks ─────────────────────────────────────────
    if broker == "groww_stocks":
        # Find header row: Stock Name | ISIN | Quantity | Average buy price | Buy value | Closing price | Closing value
        header_row = None
        for i, row in enumerate(rows):
            if row and str(row[0]).strip().lower() in ("stock name", "scrip name", "symbol"):
                header_row = i
                break

        if header_row is None:
            raise HTTPException(status_code=400, detail="Could not find header row. Expected 'Stock Name' column.")

        # Replace previous import — re-importing must not duplicate holdings
        db.query(Investment).filter(Investment.platform == "Groww",
                                    Investment.asset_class != "mutual_funds").delete()

        for row in rows[header_row + 1:]:
            if not row or not row[0]:
                continue
            name         = str(row[0]).strip()
            isin         = str(row[1]).strip() if row[1] else ""
            qty          = safe_float(row[2])
            avg_buy      = safe_float(row[3])
            buy_value    = safe_float(row[4])
            closing_px   = safe_float(row[5])
            closing_val  = safe_float(row[6])
            unrealised   = safe_float(row[7]) if len(row) > 7 else 0

            if not name or qty == 0:
                skipped += 1
                continue

            # Try to find Yahoo symbol from ISIN map
            yahoo_symbol = ISIN_TO_YAHOO.get(isin, "")

            # Classify asset type by name/ISIN
            name_up = name.upper()
            if "GOLDBOND" in name_up or "GOLD BOND" in name_up or isin == "IN0020220110":
                asset_class = "sgb"
            elif any(x in name_up for x in ["GOLDBEES","GOLDCASE","GOLDIETF","GOLD ETF"]):
                asset_class = "gold_etf"
            elif any(x in name_up for x in ["SILVER","SILVERIETF"]):
                asset_class = "silver_etf"
            elif any(x in name_up for x in ["REIT","INVIT"]):
                asset_class = "indian_stocks"
            else:
                asset_class = "indian_stocks"

            inv = Investment(
                name=name, asset_class=asset_class, platform="Groww",
                invested_amount=buy_value if buy_value > 0 else avg_buy * qty,
                current_value=closing_val if closing_val > 0 else closing_px * qty,
                units=qty, symbol=yahoo_symbol, notes=f"ISIN: {isin}",
            )
            db.add(inv)
            imported += 1

    # ── Groww Mutual Funds ───────────────────────────────────
    elif broker == "groww_mf":
        # Header row has: Scheme Name | AMC | Category | Sub-category | Folio No. | Source | Units | Invested Value | Current Value | Returns | XIRR
        header_row = None
        for i, row in enumerate(rows):
            if row and str(row[0]).strip().lower() in ("scheme name", "fund name"):
                header_row = i
                break

        if header_row is None:
            raise HTTPException(status_code=400, detail="Could not find 'Scheme Name' header row in MF file.")

        db.query(Investment).filter(Investment.platform == "Groww",
                                    Investment.asset_class == "mutual_funds").delete()

        seen_folios = set()
        for row in rows[header_row + 1:]:
            if not row or not row[0]:
                continue
            name        = str(row[0]).strip()
            amc         = str(row[1]).strip() if row[1] else ""
            category    = str(row[2]).strip() if row[2] else ""
            folio       = str(row[4]).strip() if row[4] else ""
            units       = safe_float(row[6])
            invested    = safe_float(row[7])
            current_val = safe_float(row[8])

            if not name or invested == 0:
                skipped += 1
                continue

            inv = Investment(
                name=name, asset_class="mutual_funds", platform="Groww",
                invested_amount=invested, current_value=current_val,
                units=units, symbol="",
                notes=f"AMC: {amc} | Category: {category} | Folio: {folio}",
            )
            db.add(inv)
            imported += 1

    # ── INDMoney US Stocks / CoinSwitch Crypto ───────────────
    # INDmoney "INDHOLDINGS" report (legacy .xls) looks like:
    #   Stock Symbol | Holding Since | Quantity | Avg. Price ($) | Total Value ($)
    # Quantities are FRACTIONAL shares (0.2097 AAPL) and money is in USD.
    # "Total Value ($)" is qty × avg price — i.e. cost basis, not market
    # value — so current_value starts at cost and Live Prices updates it.
    elif broker in ("indmoney", "coinswitch"):
        platform, asset_class = (
            ("INDMoney", "us_stocks") if broker == "indmoney" else ("CoinSwitch", "crypto")
        )

        def cellstr(c):
            return str(c).strip().lower() if c is not None else ""

        header_row = None
        for i, row in enumerate(rows):
            if not row:
                continue
            cells = [cellstr(c) for c in row]
            has_id  = any(k in c for c in cells for k in ("symbol", "stock", "name", "coin", "ticker"))
            has_qty = any(k in c for c in cells for k in ("quantity", "qty", "units", "shares"))
            if has_id and has_qty:
                header_row = i
                break
        if header_row is None:
            raise HTTPException(status_code=400,
                                detail=f"Could not find the holdings table in this {platform} file "
                                       "(expected Symbol/Name and Quantity columns).")

        headers = [cellstr(c) for c in rows[header_row]]

        def col(*options):
            for j, h in enumerate(headers):
                if any(o in h for o in options):
                    return j
            return None

        sc  = col("symbol", "ticker")
        nc  = col("name")
        if nc is None: nc = sc if sc is not None else col("stock", "coin")
        qc  = col("quantity", "qty", "units", "shares")
        apc = col("avg", "average")                    # avg buy price
        ic  = col("invested", "buy value", "cost")
        cc  = col("current", "market", "present")
        tvc = col("total value")
        # money columns marked with $/USD mean the file needs FX conversion
        is_usd = any(("$" in h) or ("usd" in h) for h in headers)
        usd_inr = fetch_usd_inr() if is_usd else 1.0

        db.query(Investment).filter(Investment.platform == platform).delete()

        for row in rows[header_row + 1:]:
            if not row:
                continue
            name   = str(row[nc]).strip() if nc is not None and nc < len(row) and row[nc] else ""
            symbol = str(row[sc]).strip() if sc is not None and sc < len(row) and row[sc] else ""
            qty    = safe_float(row[qc])  if qc is not None and qc < len(row) else 0
            avg_px = safe_float(row[apc]) if apc is not None and apc < len(row) else 0
            invested = safe_float(row[ic])  if ic is not None and ic < len(row) else 0
            current  = safe_float(row[cc])  if cc is not None and cc < len(row) else 0
            total_v  = safe_float(row[tvc]) if tvc is not None and tvc < len(row) else 0

            if invested == 0:
                invested = total_v if total_v > 0 else qty * avg_px
            if current == 0:
                # no market value in the file — start at cost, Live Prices refreshes it
                current = total_v if total_v > 0 else invested

            if not name or qty == 0 or invested == 0:
                skipped += 1
                continue

            notes = ""
            if is_usd:
                notes = f"Cost ${invested:,.2f} @ USD/INR {usd_inr:.2f}"
                if avg_px > 0:
                    notes += f" | Avg buy ${avg_px:,.2f}"
            inv = Investment(
                name=name, asset_class=asset_class, platform=platform,
                invested_amount=round(invested * usd_inr, 2),
                current_value=round(current * usd_inr, 2),
                units=qty,  # fractional shares preserved exactly
                symbol=symbol,
                currency="USD" if is_usd else "INR",
                fx_rate=usd_inr if is_usd else 0.0,
                notes=notes,
            )
            db.add(inv)
            imported += 1

    else:
        raise HTTPException(status_code=400, detail=f"Unknown broker: {broker}. Use groww_stocks, groww_mf, indmoney, or coinswitch")

    db.commit()
    return {
        "message": f"Successfully imported {imported} investments ({skipped} rows skipped)",
        "imported": imported,
        "skipped": skipped,
        "broker": broker,
    }


@router.post("/import-xlsx")
async def import_xlsx(broker: str, file: UploadFile = File(...),
                      password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """
    Parse broker exports: groww_stocks | groww_mf | indmoney | coinswitch.
    Supports .xlsx, legacy .xls, and password-protected files.
    """
    content = await file.read()
    content = decrypt_xlsx_if_needed(content, password)
    rows = load_workbook_rows(content)
    try:
        return run_broker_import(broker, rows, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")


# Keep old CSV endpoint for backwards compat
@router.post("/import-csv")
async def import_csv(broker: str, file: UploadFile = File(...),
                     password: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return await import_xlsx(broker=broker, file=file, password=password, db=db)
