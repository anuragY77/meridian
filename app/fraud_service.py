# app/fraud_service.py
import json
import time
import logging
from datetime import datetime

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from prometheus_client import start_http_server

from app.config import settings
from app.database import SessionLocal, FraudFlag
from app.fraud_engine import evaluate_transaction
from app.metrics import fraud_flags_total

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-FRAUD] %(message)s")
logger = logging.getLogger(__name__)

METRICS_PORT = 9101


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
                group_id="meridian-fraud-group",
            )
        except NoBrokersAvailable:
            logger.warning(f"Redpanda not ready, retrying... ({attempt + 1}/5)")
            time.sleep(3)
    raise ConnectionError("Could not connect to Redpanda after 5 attempts.")


def run_fraud_service():
    start_http_server(METRICS_PORT)
    logger.info(f"Metrics server started on :{METRICS_PORT}/metrics")

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
                        fraud_flags_total.labels(rule=flag["rule_triggered"]).inc()
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
