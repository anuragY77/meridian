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
    """
    Records every fraud/risk flag raised by the fraud engine, with an
    explicit, human-readable reason — never a bare score. This is what
    lets a reviewer (or an interviewer) see WHY something was flagged,
    not just THAT it was flagged.
    """
    __tablename__ = "fraud_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    rule_triggered = Column(String, nullable=False)   # "VELOCITY", "CARD_TESTING", "AMOUNT_ANOMALY"
    reason = Column(Text, nullable=False)             # human-readable explanation
    severity = Column(String, default="medium")       # "low", "medium", "high"
    flagged_at = Column(DateTime, default=datetime.utcnow, index=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
