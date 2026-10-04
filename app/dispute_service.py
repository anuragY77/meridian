"""
Simulates the merchant-dispute lifecycle with RBI-style mandated
resolution SLAs. Two jobs run on a timer:
  1. Raise new disputes against a small sample of recent successful
     transactions (simulating customers filing complaints).
  2. Check all open disputes against their SLA deadline — auto-resolve
     some (simulating a support team working through the queue) and
     mark any that blew past deadline as "breached".

Also closes the loop with Phase 6: if a resolved dispute's transaction
was previously fraud-flagged but the dispute confirms the transaction
was legitimate, it's recorded as a false positive — this is the
concrete, measurable version of the "false-positive account freeze"
merchant pain-point found during the original research phase.
"""
import random
import time
import logging
from datetime import datetime, timedelta

from app.database import init_db, SessionLocal, Transaction, Dispute, FraudFlag

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-DISPUTE] %(message)s")
logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 20
DISPUTE_RAISE_RATE = 0.015           # ~1.5% of eligible successful txns get a dispute per cycle
SLA_RESOLUTION_DAYS = 7               # RBI-style "7 working days" style deadline (simplified, no business-day calc)
RESOLUTION_CHANCE_PER_CHECK = 0.35    # chance an open dispute gets resolved on any given check cycle

DISPUTE_TYPES = ["unauthorized", "goods_not_received", "duplicate_charge"]
# Most disputes, once investigated, turn out NOT to be fraud (false positive
# rate here is deliberately high-ish to make the pain-point visible/measurable)
FALSE_POSITIVE_PROBABILITY = 0.70


def raise_new_disputes():
    db = SessionLocal()
    try:
        already_disputed_ids = {row[0] for row in db.query(Dispute.transaction_id).all()}

        candidates = db.query(Transaction).filter(
            Transaction.status == "success",
        ).limit(2000).all()

        raised = 0
        for txn in candidates:
            if txn.transaction_id in already_disputed_ids:
                continue
            if random.random() > DISPUTE_RAISE_RATE:
                continue

            now = datetime.utcnow()
            dispute = Dispute(
                transaction_id=txn.transaction_id,
                merchant_id=txn.merchant_id,
                customer_id=txn.customer_id,
                dispute_type=random.choice(DISPUTE_TYPES),
                status="open",
                raised_at=now,
                sla_deadline=now + timedelta(days=SLA_RESOLUTION_DAYS),
            )
            db.add(dispute)
            raised += 1

        db.commit()
        return raised
    except Exception as e:
        db.rollback()
        logger.error(f"Error raising disputes: {e}")
        return 0
    finally:
        db.close()


def check_sla_and_resolve():
    db = SessionLocal()
    try:
        open_disputes = db.query(Dispute).filter(Dispute.status == "open").all()
        now = datetime.utcnow()

        resolved_count = 0
        breached_count = 0

        for dispute in open_disputes:
            is_past_deadline = now > dispute.sla_deadline

            if is_past_deadline:
                dispute.status = "breached"
                breached_count += 1
                logger.warning(
                    f"SLA BREACH: dispute #{dispute.id} (txn {dispute.transaction_id[:8]}...) "
                    f"missed its {SLA_RESOLUTION_DAYS}-day deadline"
                )
                continue

            if random.random() < RESOLUTION_CHANCE_PER_CHECK:
                was_fraud_flagged = db.query(FraudFlag).filter(
                    FraudFlag.transaction_id == dispute.transaction_id
                ).first() is not None

                if was_fraud_flagged:
                    # Resolve it — most of the time the flag turns out to
                    # have been a false positive (the measurable version
                    # of the merchant "account freeze" pain-point)
                    was_false_positive = random.random() < FALSE_POSITIVE_PROBABILITY
                else:
                    was_false_positive = None  # not applicable — was never flagged

                dispute.status = "resolved"
                dispute.resolved_at = now
                dispute.was_false_positive = was_false_positive
                dispute.resolution_note = (
                    "Confirmed legitimate transaction — fraud flag was a false positive"
                    if was_false_positive
                    else ("Dispute upheld — transaction confirmed fraudulent" if was_fraud_flagged
                          else "Dispute resolved in merchant's favor")
                )
                resolved_count += 1

        db.commit()
        return resolved_count, breached_count
    except Exception as e:
        db.rollback()
        logger.error(f"Error checking SLA/resolving disputes: {e}")
        return 0, 0
    finally:
        db.close()


def run_dispute_service():
    init_db()
    logger.info(f"Meridian dispute/SLA service started. Checking every {CHECK_INTERVAL_SECONDS}s...")

    try:
        while True:
            raised = raise_new_disputes()
            resolved, breached = check_sla_and_resolve()

            if raised or resolved or breached:
                logger.info(f"Cycle: {raised} raised, {resolved} resolved, {breached} newly breached.")

            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Dispute/SLA service stopped.")


if __name__ == "__main__":
    run_dispute_service()
