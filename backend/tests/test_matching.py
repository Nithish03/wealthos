"""Tests for the D6 domain module (matching.py) — pure-function coverage.
Run: cd backend && venv/bin/python -m pytest tests/ -q"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from types import SimpleNamespace as NS
from matching import (bank_txn_key, cc_txn_key, filter_new, merchant_key,
                      find_recurring, find_anomalies, find_charges)

D = datetime


def test_bank_key_normalizes_case_and_time():
    a = bank_txn_key(D(2026, 6, 1, 10, 30), 500.004, 0, " Zomato Order ")
    b = bank_txn_key(D(2026, 6, 1, 18, 0), 500.0, 0.0, "zomato order")
    assert a == b


def test_filter_new_skips_duplicates():
    t1 = {"transaction_date": D(2026, 6, 1), "debit_amount": 100.0, "credit_amount": 0, "description": "X"}
    t2 = dict(t1)
    keyfn = lambda t: bank_txn_key(t["transaction_date"], t["debit_amount"], t["credit_amount"], t["description"])
    new, dups = filter_new([t1, t2], set(), keyfn)
    assert len(new) == 1 and dups == 1


def test_filter_new_respects_existing():
    t = {"transaction_date": D(2026, 6, 1), "debit_amount": 100.0, "credit_amount": 0, "description": "X"}
    keyfn = lambda t: bank_txn_key(t["transaction_date"], t["debit_amount"], t["credit_amount"], t["description"])
    new, dups = filter_new([t], {keyfn(t)}, keyfn)
    assert new == [] and dups == 1


def test_merchant_key_strips_noise():
    assert merchant_key("UPI/519912/ZOMATO LTD/4821") == merchant_key("UPI ZOMATO LTD 9932")
    assert "zomato" in merchant_key("UPI-ZOMATO ORDER 8829")


def test_recurring_needs_three_months_and_stable_amounts():
    items = [(D(2026, m, 1), 199.0, "NETFLIX SUBSCRIPTION") for m in (4, 5, 6)]
    out = find_recurring(items)
    assert len(out["items"]) == 1 and out["monthly_burn"] == 199.0
    # two months only → not recurring
    out2 = find_recurring(items[:2])
    assert out2["items"] == []
    # wildly varying amounts → not recurring
    items3 = [(D(2026, 4, 1), 100.0, "SHOP X"), (D(2026, 5, 1), 900.0, "SHOP X"), (D(2026, 6, 1), 150.0, "SHOP X")]
    assert find_recurring(items3)["items"] == []


def test_anomaly_spike_and_duplicate():
    now = D(2026, 7, 12)
    hist = [(D(2026, m, 5), 400.0, "BIG BAZAAR STORE", "card") for m in (2, 3, 4)]
    spike = [(D(2026, 7, 1), 2000.0, "BIG BAZAAR STORE", "card")]
    dup = [(D(2026, 7, 3), 999.0, "AIRTEL RECHARGE", "bank"), (D(2026, 7, 4), 999.0, "AIRTEL RECHARGE", "bank")]
    alerts = find_anomalies(hist + spike + dup, days=60, now=now)
    kinds = {a["type"] for a in alerts}
    assert "spike" in kinds and "duplicate" in kinds


def test_charges_watchdog():
    txns = [
        NS(transaction_type="debit", description="EMI INTEREST - 3/3", category="Finance Charges",
           amount=138.55, transaction_date=D(2026, 6, 10)),
        NS(transaction_type="debit", description="IGST-CI@18%", category="Other",
           amount=24.94, transaction_date=D(2026, 6, 10)),
        NS(transaction_type="debit", description="ZOMATO ORDER", category="Food & Dining",
           amount=500.0, transaction_date=D(2026, 6, 11)),
        NS(transaction_type="credit", description="LATE FEE REVERSAL", category="Finance Charges",
           amount=500.0, transaction_date=D(2026, 6, 12)),
    ]
    out = find_charges(txns, now=D(2026, 7, 12))
    assert out["total_6m"] == 163.49          # interest + gst, not food, not the credit
    assert len(out["items"]) == 2
