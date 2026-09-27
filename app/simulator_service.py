import json
import time
import logging

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from app.config import settings
from app.transaction_generator import generate_transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-SIM] %(message)s")
logger = logging.getLogger(__name__)


def get_kafka_producer() -> KafkaProducer:
    for attempt in range(5):
        try:
            return KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
        except NoBrokersAvailable:
            logger.warning(f"Redpanda not ready, retrying... ({attempt + 1}/5)")
            time.sleep(3)
    raise ConnectionError("Could not connect to Redpanda after 5 attempts.")


def run_simulator():
    producer = get_kafka_producer()
    sleep_interval = 1.0 / settings.simulator_tps

    logger.info(
        f"Starting Meridian simulator — {settings.simulator_tps} txns/sec, "
        f"publishing to topic '{settings.kafka_topic_transactions}'"
    )

    count = 0
    try:
        while True:
            txn = generate_transaction()

            producer.send(
                settings.kafka_topic_transactions,
                key=txn["merchant_id"],
                value=txn,
            )

            count += 1
            if count % 10 == 0:
                producer.flush()
                logger.info(f"Published {count} transactions. Last: {txn['transaction_id'][:8]}...")

            time.sleep(sleep_interval)

    except KeyboardInterrupt:
        producer.flush()
        producer.close()
        logger.info(f"Simulator stopped. Total transactions published: {count}")


if __name__ == "__main__":
    run_simulator()