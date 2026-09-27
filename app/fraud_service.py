# app/fraud_service.py
"""
Standalone fraud-detection consumer — reads from the SAME Kafka topic as
processor_service.py, but as an independent consumer group, so it runs in
parallel without any coupling to (or slowing down) the core routing path.
This is the same "plug fraud detection on top of the stream, don't touch
core routing" design decided back in Phase 0.
Run with: python -m app.fraud_service
"""
import json
import time
import logging
from datetime import datetime

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from app.config import settings
from app.database import init_db, SessionLocal, FraudFlag
from app.fraud_engine import evaluate_transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-FRAUD] %(message)s")
logger = logging.getLogger(__name__)


def get_kafka_consumer() -> KafkaConsumer:
    for attempt in range(5):
        try:
            return KafkaConsumer(
                settings.kafka_topic_transactions,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                group_id="meridian-fraud-group",   # separate consumer group — independent offset tracking
            )
        except NoBrokersAvailable:
            logger.warning(f"Redpanda not ready, retrying... ({attempt + 1}/5)")
            time.sleep(3)
    raise ConnectionError("Could not connect to Redpanda after 5 attempts.")


def run_fraud_service():
    init_db()
    consumer = get_kafka_consumer()
    logger.info("Meridian fraud engine started. Listening on 'transactions_raw' (independent of routing)...")

    flagged_count = 0
    total_count = 0

    try:
        for message in consumer:
            txn = message.value
            timestamp = datetime.fromisoformat(txn["created_at"])
            total_count += 1

            flags = evaluate_transaction(txn, timestamp)

            if flags:
                flagged_count += 1
                db = SessionLocal()
                try:
                    for flag in flags:
                        db.add(FraudFlag(
                            transaction_id=txn["transaction_id"],
                            customer_id=txn["customer_id"],
                            rule_triggered=flag["rule_triggered"],
                            reason=flag["reason"],
                            severity=flag["severity"],
                            flagged_at=timestamp,
                        ))
                    db.commit()
                    for flag in flags:
                        logger.warning(
                            f"FLAGGED txn={txn['transaction_id'][:8]}... "
                            f"[{flag['rule_triggered']}/{flag['severity']}] {flag['reason']}"
                        )
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error saving fraud flag: {e}")
                finally:
                    db.close()

            if total_count % 100 == 0:
                logger.info(f"Processed {total_count} transactions, {flagged_count} flagged so far.")

    except KeyboardInterrupt:
        logger.info(f"Fraud engine stopped. Total processed: {total_count}, flagged: {flagged_count}.")
    finally:
        consumer.close()


if __name__ == "__main__":
    run_fraud_service()
