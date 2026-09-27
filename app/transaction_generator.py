# app/transaction_generator.py
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

from app.gateways import PaymentMethod

fake = Faker("en_IN")

METHOD_WEIGHTS = {"UPI": 0.55, "CARD": 0.25, "NETBANKING": 0.10, "WALLET": 0.10}

MERCHANT_POOL = [
    "TechMart Electronics", "QuickGrocery", "StyleHub Fashion",
    "FoodExpress", "BookNest", "TravelEase", "HomeDecor Plus",
    "FitGear Sports", "PetCare Store", "EduLearn Courses",
]

# Small pool of "suspicious" identities reused deliberately, so fraud
# patterns (velocity, card-testing) actually have a chance to occur in
# a short simulator run — mirrors how real fraud rings reuse a small
# set of stolen identities/cards across many attempts.
FRAUD_INJECTION_RATE = 0.08   # 8% of transactions deliberately drawn from this pool
SUSPICIOUS_CUSTOMER_IDS = [f"cust_{i}" for i in range(90000, 90005)]
SUSPICIOUS_CARDS = [f"{i}" for i in range(9001, 9004)]


def generate_synthetic_timestamp() -> datetime:
    now = datetime.utcnow()
    days_back = random.randint(0, 30)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    dt = now - timedelta(days=days_back)
    return dt.replace(hour=hour, minute=minute, second=second, microsecond=0)


def generate_transaction() -> dict:
    method: PaymentMethod = random.choices(
        list(METHOD_WEIGHTS.keys()), weights=list(METHOD_WEIGHTS.values()), k=1
    )[0]

    is_injected_fraud_pattern = random.random() < FRAUD_INJECTION_RATE

    if is_injected_fraud_pattern:
        customer_id = random.choice(SUSPICIOUS_CUSTOMER_IDS)
        if method != "CARD":
            method = "CARD"
        card_suffix = random.choice(SUSPICIOUS_CARDS)
        amount = round(random.uniform(50000, 100000), 2)
        # Cluster fraud-pattern timestamps within a tight, shared window
        # (using wall-clock "now" so real-time-based Redis rules can
        # actually observe the burst as it streams through)
        synthetic_ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 120))
    else:
        customer_id = f"cust_{random.randint(10000, 99999)}"
        card_suffix = fake.credit_card_number()[-4:] if method == "CARD" else None
        if random.random() < 0.85:
            amount = round(random.uniform(100, 5000), 2)
        else:
            amount = round(random.uniform(5000, 100000), 2)
        synthetic_ts = generate_synthetic_timestamp()

    return {
        "transaction_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "merchant_id": f"merch_{random.randint(1000, 1050)}",
        "merchant_name": random.choice(MERCHANT_POOL),
        "customer_id": customer_id,
        "amount": amount,
        "currency": "INR",
        "method": method,
        "card_last4": card_suffix,
        "created_at": synthetic_ts.isoformat(),
    }
