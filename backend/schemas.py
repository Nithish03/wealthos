from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


# Auth
class PINSetup(BaseModel):
    pin: str

class PINLogin(BaseModel):
    pin: str

class Token(BaseModel):
    access_token: str
    token_type: str


# Investment
class InvestmentBase(BaseModel):
    name: str
    asset_class: str
    platform: Optional[str] = ""
    invested_amount: Optional[float] = 0.0
    current_value: Optional[float] = 0.0
    units: Optional[float] = 0.0
    symbol: Optional[str] = ""
    notes: Optional[str] = ""

class InvestmentCreate(InvestmentBase):
    pass

class InvestmentUpdate(BaseModel):
    name: Optional[str] = None
    asset_class: Optional[str] = None
    platform: Optional[str] = None
    invested_amount: Optional[float] = None
    current_value: Optional[float] = None
    units: Optional[float] = None
    symbol: Optional[str] = None
    notes: Optional[str] = None

class InvestmentOut(InvestmentBase):
    id: int
    last_updated: datetime
    created_at: datetime
    pnl: Optional[float] = 0.0
    pnl_percent: Optional[float] = 0.0

    class Config:
        from_attributes = True


# Credit Card
class CreditCardBase(BaseModel):
    name: str
    bank: str
    card_number_masked: Optional[str] = ""
    credit_limit: Optional[float] = 0.0
    available_credit: Optional[float] = 0.0
    available_cash_limit: Optional[float] = 0.0
    current_balance: Optional[float] = 0.0   # kept for compat
    total_due: Optional[float] = 0.0
    minimum_due: Optional[float] = 0.0
    payment_due_date: Optional[date] = None
    statement_date: Optional[date] = None
    billing_start: Optional[date] = None
    billing_end: Optional[date] = None
    statement_day: Optional[int] = 1
    due_day: Optional[int] = 20

class CreditCardCreate(CreditCardBase):
    pass

class CreditCardUpdate(BaseModel):
    name: Optional[str] = None
    bank: Optional[str] = None
    card_number_masked: Optional[str] = None
    credit_limit: Optional[float] = None
    available_credit: Optional[float] = None
    available_cash_limit: Optional[float] = None
    current_balance: Optional[float] = None
    total_due: Optional[float] = None
    minimum_due: Optional[float] = None
    payment_due_date: Optional[date] = None
    statement_day: Optional[int] = None
    due_day: Optional[int] = None

class CreditCardOut(CreditCardBase):
    id: int
    created_at: datetime
    utilization_percent: Optional[float] = 0.0

    class Config:
        from_attributes = True


# Credit Card Transaction
class TransactionBase(BaseModel):
    card_id: int
    amount: float
    # None (not "Other") so the router can auto-categorize from the description
    category: Optional[str] = None
    description: Optional[str] = ""
    transaction_date: Optional[datetime] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionOut(TransactionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Bank Account
class BankAccountBase(BaseModel):
    name: str
    bank: str
    purpose: Optional[str] = ""
    balance: Optional[float] = 0.0
    monthly_inflow: Optional[float] = 0.0
    monthly_outflow: Optional[float] = 0.0
    is_emergency_fund: Optional[bool] = False

class BankAccountCreate(BankAccountBase):
    pass

class BankAccountUpdate(BaseModel):
    name: Optional[str] = None
    bank: Optional[str] = None
    purpose: Optional[str] = None
    balance: Optional[float] = None
    monthly_inflow: Optional[float] = None
    monthly_outflow: Optional[float] = None
    is_emergency_fund: Optional[bool] = None

class BankAccountOut(BankAccountBase):
    id: int
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# Net Worth Snapshot
class NetWorthSnapshotBase(BaseModel):
    total_assets: float
    total_liabilities: float
    net_worth: float
    investment_value: float
    bank_balance: float
    credit_dues: float
    notes: Optional[str] = ""

class NetWorthSnapshotOut(NetWorthSnapshotBase):
    id: int
    snapshot_date: datetime

    class Config:
        from_attributes = True
