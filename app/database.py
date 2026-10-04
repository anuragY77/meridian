# app/database.py
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Text, Boolean
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

    reconciliation_status = Column(String, default="pending")
    settled_at = Column(DateTime, default=datetime.utcnow, index=True)


class Dispute(Base):
    """
    Tracks a merchant/customer dispute raised against a successful
    transaction, with an RBI-style mandated resolution deadline.
    `was_false_positive` links back to Phase 6's fraud_flags: if a
    transaction was fraud-flagged but the dispute later confirms it was
    legitimate, this captures exactly the merchant pain-point the earlier
    research surfaced (false-positive account/transaction flags).
    """
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False, index=True)
    merchant_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)

    dispute_type = Column(String, nullable=False)   # "unauthorized", "goods_not_received", "duplicate_charge"
    status = Column(String, default="open", index=True)  # open, resolved, breached
    was_false_positive = Column(Boolean, nullable=True)   # null until resolved

    raised_at = Column(DateTime, default=datetime.utcnow, index=True)
    sla_deadline = Column(DateTime, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
