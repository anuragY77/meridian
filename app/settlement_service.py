# app/settlement_service.py
import time
import logging

from prometheus_client import start_http_server

from app.database import SessionLocal, Transaction, Settlement
from app.fx_rates import convert_to_inr
from app.metrics import settlements_processed_total, reconciliation_mismatches_total

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-SETTLEMENT] %(message)s")
logger = logging.getLogger(__name__)

METRICS_PORT = 9102
BATCH_INTERVAL_SECONDS = 30
RECONCILIATION_TOLERANCE = 0.01


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

            settlements_processed_total.labels(currency=breakdown["original_currency"]).inc()
            if not is_matched:
                reconciliation_mismatches_total.inc()
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
    start_http_server(METRICS_PORT)
    logger.info(f"Metrics server started on :{METRICS_PORT}/metrics")
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
