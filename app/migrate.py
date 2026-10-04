"""
Explicit, one-time schema migration step — run this ONCE before starting
any services. Keeping this separate from each service's startup avoids the
race condition where multiple services simultaneously try to CREATE TABLE
on first boot (a common real-world issue when several microservices share
one database and each tries to self-initialize on startup).

Run with: python -m app.migrate
"""
import logging

from app.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MERIDIAN-MIGRATE] %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Running schema migration (create tables if not exist)...")
    init_db()
    logger.info("Migration complete. Safe to start services now.")
