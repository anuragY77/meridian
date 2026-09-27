# app/database.py
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

from app.config import settings

engine = create_engine(settings.postgres_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True)
    idempotency_key = Column(String, unique=True, nullable=False, index=True)
    merchant_id = Column(String, nullable=False, index=True)
    merchant_name = Column(String)
    customer_id = Column(String, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    method = Column(String, nullable=False)

    status = Column(String, default="pending", index=True)

    chosen_gateway_id = Column(String, nullable=True)
    attempt_count = Column(Integer, default=0)
    last_decline_code = Column(String, nullable=True)
    last_latency_ms = Column(Integer, nullable=True)
    routing_strategy = Column(String, nullable=True, index=True)

    attempts_log = Column(Text, nullable=True)
    card_last4 = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reconciled_at = Column(DateTime, nullable=True)


class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    rule_triggered = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    severity = Column(String, default="medium")
    flagged_at = Column(DateTime, default=datetime.utcnow, index=True)


class Settlement(Base):
    """
    Represents the settlement of ONE successful cross-border transaction
    into INR. Kept as a separate table (not columns on Transaction) because
    settlement is conceptually a distinct downstream event — a transaction
    can succeed at the gateway level well before it's actually settled,
    exactly like real payment aggregators.
    """
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False, unique=True, index=True)
    merchant_id = Column(String, nullable=False, index=True)

    original_amount = Column(Float, nullable=False)
    original_currency = Column(String, nullable=False)
    fx_rate_used = Column(Float, nullable=False)
    gross_inr = Column(Float, nullable=False)
    conversion_fee_inr = Column(Float, nullable=False)
    net_settlement_inr = Column(Float, nullable=False)

    reconciliation_status = Column(String, default="pending")  # pending, matched, mismatch
    settled_at = Column(DateTime, default=datetime.utcnow, index=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
