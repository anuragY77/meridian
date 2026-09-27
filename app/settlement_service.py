"""
Standalone settlement service — periodically scans for successful,
non-INR transactions that haven't been settled yet, converts them to INR
via fx_rates, and writes a Settlement record with a full reconciliation
check (does net + fee == gross, within floating-point tolerance?).

Runs as a periodic batch job (not a live Kafka consumer) because real
settlement in payment systems is typically a batch/cycle process (e.g.
T+1, T+2 settlement cycles), not an instant per-transaction event —
this mirrors that reality rather than pretending settlement is instant.
"""
import time
import logging

from app.database import init_db, SessionLocal, Transaction, Settlement
from app.fx_rates import convert_to_inr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-SETTLEMENT] %(message)s")
logger = logging.getLogger(__name__)

BATCH_INTERVAL_SECONDS = 30
RECONCILIATION_TOLERANCE = 0.01  # 1 paisa tolerance for floating-point rounding


def process_pending_settlements() -> int:
    db = SessionLocal()
    processed = 0
    try:
        already_settled_ids = {row[0] for row in db.query(Settlement.transaction_id).all()}

        candidates = db.query(Transaction).filter(
            Transaction.status == "success",
            Transaction.currency != "INR",
        ).all()

        for txn in candidates:
            if txn.transaction_id in already_settled_ids:
                continue

            breakdown = convert_to_inr(txn.amount, txn.currency)

            # Reconciliation check: net + fee should equal gross, within tolerance.
            # This is a deliberately simple self-consistency check — in a real
            # system reconciliation also cross-checks against the bank's/PSP's
            # own settlement report, which this simulation doesn't have access to.
            reconstructed_gross = breakdown["net_settlement_inr"] + breakdown["conversion_fee_inr"]
            is_matched = abs(reconstructed_gross - breakdown["gross_inr"]) <= RECONCILIATION_TOLERANCE

            settlement = Settlement(
                transaction_id=txn.transaction_id,
                merchant_id=txn.merchant_id,
                original_amount=breakdown["original_amount"],
                original_currency=breakdown["original_currency"],
                fx_rate_used=breakdown["fx_rate_used"],
                gross_inr=breakdown["gross_inr"],
                conversion_fee_inr=breakdown["conversion_fee_inr"],
                net_settlement_inr=breakdown["net_settlement_inr"],
                reconciliation_status="matched" if is_matched else "mismatch",
            )
            db.add(settlement)
            processed += 1

            if not is_matched:
                logger.error(
                    f"RECONCILIATION MISMATCH for txn {txn.transaction_id[:8]}...: "
                    f"gross={breakdown['gross_inr']}, reconstructed={reconstructed_gross}"
                )

        db.commit()
        return processed
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing settlements: {e}")
        return 0
    finally:
        db.close()


def run_settlement_service():
    init_db()
    logger.info(f"Meridian settlement service started. Processing every {BATCH_INTERVAL_SECONDS}s...")

    try:
        while True:
            count = process_pending_settlements()
            if count > 0:
                logger.info(f"Settled {count} new cross-border transaction(s).")
            time.sleep(BATCH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Settlement service stopped.")


if __name__ == "__main__":
    run_settlement_service()
