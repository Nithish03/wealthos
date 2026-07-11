from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    pin_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Investment(Base):
    __tablename__ = "investments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    asset_class = Column(String, nullable=False)
    platform = Column(String, default="")
    invested_amount = Column(Float, default=0.0)   # always INR
    current_value = Column(Float, default=0.0)     # always INR
    units = Column(Float, default=0.0)
    symbol = Column(String, default="")
    notes = Column(Text, default="")
    currency = Column(String, default="INR")        # source currency: INR or USD
    fx_rate = Column(Float, default=0.0)            # USD/INR rate at import
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class CreditCard(Base):
    __tablename__ = "credit_cards"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    bank = Column(String, nullable=False)
    card_number_masked = Column(String, default="")

    # Limits
    credit_limit = Column(Float, default=0.0)
    available_credit = Column(Float, default=0.0)
    available_cash_limit = Column(Float, default=0.0)

    # Statement amounts — populated from PDF import
    total_due = Column(Float, default=0.0)
    minimum_due = Column(Float, default=0.0)
    payment_due_date = Column(Date, nullable=True)

    # Statement period
    statement_date = Column(Date, nullable=True)
    billing_start = Column(Date, nullable=True)
    billing_end = Column(Date, nullable=True)

    # Backward compat
    current_balance = Column(Float, default=0.0)
    statement_day = Column(Integer, default=1)
    due_day = Column(Integer, default=20)

    created_at = Column(DateTime, default=datetime.utcnow)
    transactions = relationship("CreditCardTransaction", back_populates="card", cascade="all, delete-orphan")


class CreditCardTransaction(Base):
    __tablename__ = "credit_card_transactions"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, default="Other")
    description = Column(String, default="")
    transaction_date = Column(DateTime, default=datetime.utcnow)
    transaction_type = Column(String, default="debit")
    created_at = Column(DateTime, default=datetime.utcnow)
    card = relationship("CreditCard", back_populates="transactions")


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    bank = Column(String, nullable=False)
    purpose = Column(String, default="")
    balance = Column(Float, default=0.0)
    monthly_inflow = Column(Float, default=0.0)
    monthly_outflow = Column(Float, default=0.0)
    is_emergency_fund = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class CategoryRule(Base):
    """User-taught merchant→category mapping. pattern is a lowercase substring
    matched against transaction descriptions; learned rules override the
    built-in keyword guessers."""
    __tablename__ = "category_rules"
    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(DateTime, default=datetime.utcnow)
    total_assets = Column(Float, default=0.0)
    total_liabilities = Column(Float, default=0.0)
    net_worth = Column(Float, default=0.0)
    investment_value = Column(Float, default=0.0)
    bank_balance = Column(Float, default=0.0)
    credit_dues = Column(Float, default=0.0)
    notes = Column(Text, default="")
