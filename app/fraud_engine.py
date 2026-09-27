# app/fraud_engine.py
"""
Explainable, rule-based fraud detection. Each rule produces a specific,
human-readable reason when triggered — this is deliberately NOT a black-box
ML score, because a fraud/risk decision that a merchant or reviewer can't
understand is operationally useless (they need to know WHY to act on it).

State is kept in Redis, keyed by customer_id/card, so this can run as a
live streaming consumer without needing to re-query Postgres on every event.
"""
from datetime import datetime, timedelta

import redis

from app.config import settings

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.redis_host, port=settings.redis_port, decode_responses=True,
        )
    return _redis_client


VELOCITY_WINDOW_SECONDS = 5 * 60      # 5 minutes
VELOCITY_THRESHOLD = 3                # 3+ txns in window = flag

CARD_TESTING_WINDOW_SECONDS = 10 * 60  # 10 minutes
CARD_TESTING_MERCHANT_THRESHOLD = 3    # same card, 3+ different merchants

AMOUNT_ANOMALY_MULTIPLIER = 5.0        # 5x customer's own historical average


def check_velocity(customer_id: str, timestamp: datetime) -> dict | None:
    """Rule 1: too many transactions from the same customer in a short window."""
    r = get_redis_client()
    key = f"velocity:{customer_id}"
    ts_epoch = timestamp.timestamp()

    # Sorted set: score = timestamp, member = unique event marker
    r.zadd(key, {f"{ts_epoch}": ts_epoch})
    r.zremrangebyscore(key, 0, ts_epoch - VELOCITY_WINDOW_SECONDS)
    r.expire(key, VELOCITY_WINDOW_SECONDS * 2)

    count = r.zcard(key)
    if count >= VELOCITY_THRESHOLD:
        return {
            "rule_triggered": "VELOCITY",
            "reason": f"{count} transactions from customer {customer_id} within "
                      f"{VELOCITY_WINDOW_SECONDS // 60} minutes (threshold: {VELOCITY_THRESHOLD})",
            "severity": "high" if count >= VELOCITY_THRESHOLD + 2 else "medium",
        }
    return None


def check_card_testing(card_last4: str | None, merchant_id: str, timestamp: datetime) -> dict | None:
    """Rule 2: same card used across multiple different merchants quickly — classic card-testing pattern."""
    if not card_last4:
        return None

    r = get_redis_client()
    key = f"card_merchants:{card_last4}"
    ts_epoch = timestamp.timestamp()

    r.zadd(key, {merchant_id: ts_epoch})
    r.zremrangebyscore(key, 0, ts_epoch - CARD_TESTING_WINDOW_SECONDS)
    r.expire(key, CARD_TESTING_WINDOW_SECONDS * 2)

    distinct_merchants = r.zcard(key)
    if distinct_merchants >= CARD_TESTING_MERCHANT_THRESHOLD:
        return {
            "rule_triggered": "CARD_TESTING",
            "reason": f"Card ending {card_last4} used across {distinct_merchants} different "
                      f"merchants within {CARD_TESTING_WINDOW_SECONDS // 60} minutes",
            "severity": "high",
        }
    return None


def check_amount_anomaly(customer_id: str, amount: float) -> dict | None:
    """Rule 3: transaction amount is far above this customer's own historical average."""
    r = get_redis_client()
    key = f"customer_avg:{customer_id}"

    stored = r.hgetall(key)
    if stored and int(stored.get("count", 0)) >= 3:
        avg = float(stored["sum"]) / int(stored["count"])
        if amount >= avg * AMOUNT_ANOMALY_MULTIPLIER:
            flag = {
                "rule_triggered": "AMOUNT_ANOMALY",
                "reason": f"Amount ₹{amount:,.2f} is {amount / avg:.1f}x this customer's "
                          f"historical average of ₹{avg:,.2f}",
                "severity": "medium",
            }
        else:
            flag = None
    else:
        flag = None

    # Update running average regardless of flag outcome
    r.hincrbyfloat(key, "sum", amount)
    r.hincrby(key, "count", 1)
    r.expire(key, 60 * 60 * 24 * 30)  # 30-day rolling window

    return flag


def evaluate_transaction(txn: dict, timestamp: datetime) -> list[dict]:
    """Runs all fraud rules against one transaction, returns every flag raised."""
    flags = []

    v = check_velocity(txn["customer_id"], timestamp)
    if v:
        flags.append(v)

    c = check_card_testing(txn.get("card_last4"), txn["merchant_id"], timestamp)
    if c:
        flags.append(c)

    a = check_amount_anomaly(txn["customer_id"], txn["amount"])
    if a:
        flags.append(a)

    return flags
