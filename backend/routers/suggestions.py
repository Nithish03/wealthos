from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import Investment, CreditCard, BankAccount, CreditCardTransaction

from routers.auth import require_auth

router = APIRouter(prefix="/suggestions", tags=["suggestions"], dependencies=[Depends(require_auth)])

MONTHLY_INHAND  = 100000
ANNUAL_CTC      = 1395565
FIXED_CTC       = 1245565
PERFORMANCE_BONUS = 100000

RECOMMENDED_ALLOCATION = {
    "indian_stocks": 35, "mutual_funds": 25, "us_stocks": 15,
    "crypto": 5, "gold_etf": 5, "silver_etf": 3,
    "sgb": 5, "digital_gold": 2, "digital_silver": 5,
}
ASSET_LABELS = {
    "indian_stocks": "Indian Stocks", "mutual_funds": "Mutual Funds",
    "us_stocks": "US Stocks", "crypto": "Crypto", "gold_etf": "Gold ETF",
    "silver_etf": "Silver ETF", "sgb": "Sovereign Gold Bond",
    "digital_gold": "Digital Gold", "digital_silver": "Digital Silver",
}


def milestone_desc(label, m):
    if m["months"] == 0:
        return label + ": Already reached!"
    return label + ": ~" + str(m["years"]) + " years (" + str(m["months"]) + " months)"


def calc_milestone(current_nw, monthly_sip, annual_return, target):
    if current_nw >= target:
        return {"reached": True, "months": 0, "years": 0, "target": target, "current": round(current_nw, 0)}
    monthly_return = annual_return / 12
    months = 0
    nw = current_nw
    while nw < target and months < 600:
        nw = nw * (1 + monthly_return) + monthly_sip
        months += 1
    return {
        "reached": months < 600, "months": months,
        "years": round(months / 12, 1), "target": target, "current": round(current_nw, 0),
    }


def calc_health_score(emergency_months, spend_pct):
    score = 100
    breakdown = []
    if emergency_months < 3:
        score -= 25
        breakdown.append({"label": "Emergency Fund", "score": 0, "max": 25, "status": "critical"})
    elif emergency_months < 6:
        score -= 10
        breakdown.append({"label": "Emergency Fund", "score": 15, "max": 25, "status": "partial"})
    else:
        breakdown.append({"label": "Emergency Fund", "score": 25, "max": 25, "status": "good"})

    if spend_pct > 60:
        score -= 20
        breakdown.append({"label": "Spending Control", "score": 0, "max": 25, "status": "critical"})
    elif spend_pct > 40:
        score -= 10
        breakdown.append({"label": "Spending Control", "score": 15, "max": 25, "status": "warning"})
    else:
        breakdown.append({"label": "Spending Control", "score": 25, "max": 25, "status": "good"})

    breakdown.append({"label": "Investment Returns", "score": 25, "max": 25, "status": "good"})
    breakdown.append({"label": "Savings Rate", "score": 25, "max": 25, "status": "good"})
    grade = "A" if score >= 80 else ("B" if score >= 60 else ("C" if score >= 40 else "D"))
    return {"score": max(0, score), "grade": grade, "breakdown": breakdown}


@router.get("/")
def get_suggestions(db: Session = Depends(get_db)):
    investments = db.query(Investment).all()
    cards       = db.query(CreditCard).all()
    accounts    = db.query(BankAccount).all()

    total_investments = sum((i.current_value or 0) for i in investments)
    total_bank        = sum((a.balance or 0) for a in accounts)
    total_dues        = sum((c.total_due or c.current_balance or 0) for c in cards)
    net_worth         = total_investments + total_bank - total_dues

    now   = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    end   = datetime(now.year + 1, 1, 1) if now.month == 12 else datetime(now.year, now.month + 1, 1)
    monthly_spend = sum(
        t.amount for t in db.query(CreditCardTransaction).filter(
            CreditCardTransaction.transaction_date >= start,
            CreditCardTransaction.transaction_date < end,
            CreditCardTransaction.transaction_type == "debit"
        ).all()
    )
    spend_pct = (monthly_spend / MONTHLY_INHAND * 100) if MONTHLY_INHAND > 0 else 0

    suggestions = []

    # 1. Savings Rate
    target_savings = MONTHLY_INHAND * 0.35
    suggestions.append({
        "category": "savings",
        "title": "💰 Monthly Savings Target",
        "priority": "high",
        "details": [
            "Monthly in-hand (gross): ₹1,00,000",
            "After EPF + Income Tax, est. in-hand: ~₹72,000–75,000",
            "Target savings rate: 35% → ₹25,000–26,000/month",
            "Set up auto-debit SIPs on salary day to save before spending",
        ],
        "action": "Automate SIPs of ₹25,000/month on the 1st of every month",
    })

    # 2. SIP Breakdown
    sip_total = 25000
    sip_breakdown = {
        "Large Cap MF": 7500,
        "Mid Cap MF":   5000,
        "Indian Stocks": 3750,
        "US Index Fund": 3750,
        "Gold ETF / SGB": 2500,
        "Small Cap MF":  1250,
        "Crypto (BTC/ETH)": 1250,
    }
    suggestions.append({
        "category": "investment",
        "title": "📈 Recommended SIP Allocation",
        "priority": "high",
        "details": [k + ": ₹" + str(v) + "/month" for k, v in sip_breakdown.items()],
        "action": "Total SIP: ₹25,000/month — start with 1-2 funds and add more gradually",
        "sip_breakdown": sip_breakdown,
    })

    # 3. Portfolio Allocation
    total_portfolio = total_investments if total_investments > 0 else 1
    by_class = {}
    for inv in investments:
        by_class[inv.asset_class] = by_class.get(inv.asset_class, 0) + inv.current_value

    allocation_data = []
    details_alloc = []
    for ac, rec_pct in RECOMMENDED_ALLOCATION.items():
        actual_val = by_class.get(ac, 0)
        actual_pct = round(actual_val / total_portfolio * 100, 1) if total_portfolio > 0 else 0
        diff = actual_pct - rec_pct
        status = "over" if diff > 5 else ("under" if diff < -5 else "ok")
        allocation_data.append({
            "asset_class": ac, "label": ASSET_LABELS.get(ac, ac),
            "recommended_pct": rec_pct, "actual_pct": actual_pct,
            "diff": round(diff, 1), "status": status,
        })
        if status != "ok":
            label = ASSET_LABELS.get(ac, ac)
            details_alloc.append(label + ": " + str(actual_pct) + "% (target " + str(rec_pct) + "%)")

    suggestions.append({
        "category": "allocation",
        "title": "⚖️ Portfolio Allocation vs Target",
        "priority": "medium",
        "details": details_alloc if details_alloc else ["Portfolio allocation looks balanced!"],
        "action": "Rebalance every quarter",
        "allocation_data": allocation_data,
    })

    # 4. Credit Card Behaviour
    cc_details = []
    if spend_pct > 40:
        cc_details.append("🚨 CC spend ₹" + str(int(monthly_spend)) + " is " + str(round(spend_pct, 0)) + "% of salary — overspending!")
    else:
        cc_details.append("✅ Monthly CC spend ₹" + str(int(monthly_spend)) + " is " + str(round(spend_pct, 0)) + "% of salary — on track")
    cc_details.append("Suggested limits: Food ≤ ₹5,000 | Shopping ≤ ₹3,000 | Travel ≤ ₹5,000")
    cc_details.append("Always pay FULL outstanding before due date to avoid 36–42% APR")
    cc_details.append("Swiggy HDFC gives 10% cashback on Swiggy — route all food orders there")

    suggestions.append({
        "category": "credit",
        "title": "💳 Credit Card Behaviour",
        "priority": "high" if spend_pct > 40 else "medium",
        "details": cc_details,
        "action": "Pay full due every month — never just minimum due",
    })

    # 5. Emergency Fund
    emergency_acc     = next((a for a in accounts if a.is_emergency_fund), None)
    emergency_balance = emergency_acc.balance if emergency_acc else 0
    emergency_months  = emergency_balance / MONTHLY_INHAND if MONTHLY_INHAND > 0 else 0
    target_emergency  = MONTHLY_INHAND * 6
    gap = max(0, target_emergency - emergency_balance)

    suggestions.append({
        "category": "emergency",
        "title": "🏦 Emergency Fund Status",
        "priority": "high" if emergency_months < 3 else ("medium" if emergency_months < 6 else "low"),
        "details": [
            "Current emergency fund: ₹" + str(int(emergency_balance)) + " (" + str(round(emergency_months, 1)) + " months)",
            "Target: ₹" + str(int(target_emergency)) + " (6 months of salary)",
            "Gap to fill: ₹" + str(int(gap)),
            "Keep this in DBS account or a liquid FD — do NOT invest it in stocks",
        ],
        "action": "Top up DBS account by ₹" + str(int(gap)) + " to reach 6-month target",
        "status": "adequate" if emergency_months >= 6 else ("partial" if emergency_months >= 3 else "critical"),
    })

    # 6. Tax Planning
    pf_annual    = 21600
    elss_invested = sum(i.invested_amount for i in investments if "elss" in i.name.lower() or "tax" in i.name.lower())
    total_80c    = elss_invested + pf_annual
    remaining_80c = max(0, 150000 - total_80c)
    monthly_elss = min(remaining_80c // 12, 12500)

    suggestions.append({
        "category": "tax",
        "title": "📋 80C Tax Planning",
        "priority": "high" if remaining_80c > 50000 else "low",
        "details": [
            "80C limit: ₹1,50,000/year",
            "EPF contribution (est.): ₹" + str(pf_annual) + "/year",
            "ELSS identified: ₹" + str(int(elss_invested)),
            "Remaining 80C headroom: ₹" + str(int(remaining_80c)),
            "Note: Under New Tax Regime (default FY25-26), 80C deductions don't apply — verify your regime",
        ],
        "action": "Add ELSS SIP of ₹" + str(monthly_elss) + "/month" if remaining_80c > 0 else "80C fully utilized!",
        "remaining_80c": remaining_80c,
    })

    # 7. Wealth Milestones
    monthly_sip  = sip_total
    annual_return = 0.12
    milestones_raw   = [
        calc_milestone(net_worth, monthly_sip, annual_return, 1000000),
        calc_milestone(net_worth, monthly_sip, annual_return, 2500000),
        calc_milestone(net_worth, monthly_sip, annual_return, 5000000),
        calc_milestone(net_worth, monthly_sip, annual_return, 10000000),
    ]
    milestone_labels = ["₹10 Lakh", "₹25 Lakh", "₹50 Lakh", "₹1 Crore"]

    milestones = [{"label": l, **m} for l, m in zip(milestone_labels, milestones_raw)]
    milestone_details = [milestone_desc(l, m) for l, m in zip(milestone_labels, milestones_raw)]

    suggestions.append({
        "category": "milestones",
        "title": "🏆 Wealth Milestone Projections",
        "priority": "info",
        "details": milestone_details,
        "action": "Based on ₹25,000/month SIP at 12% CAGR",
        "milestones": milestones,
        "current_net_worth": round(net_worth, 0),
        "monthly_sip": monthly_sip,
    })

    return {
        "suggestions": suggestions,
        "salary": {
            "monthly_inhand": MONTHLY_INHAND,
            "annual_ctc": ANNUAL_CTC,
            "fixed_ctc": FIXED_CTC,
            "performance_bonus": PERFORMANCE_BONUS,
        },
        "financial_health_score": calc_health_score(emergency_months, spend_pct),
    }
