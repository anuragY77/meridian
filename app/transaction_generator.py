# app/transaction_generator.py
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

from app.gateways import PaymentMethod
from app.fx_rates import SUPPORTED_CURRENCIES

fake = Faker("en_IN")

METHOD_WEIGHTS = {"UPI": 0.55, "CARD": 0.25, "NETBANKING": 0.10, "WALLET": 0.10}

MERCHANT_POOL = [
    "TechMart Electronics", "QuickGrocery", "StyleHub Fashion",
    "FoodExpress", "BookNest", "TravelEase", "HomeDecor Plus",
    "FitGear Sports", "PetCare Store", "EduLearn Courses",
]

FRAUD_INJECTION_RATE = 0.08
SUSPICIOUS_CUSTOMER_IDS = [f"cust_{i}" for i in range(90000, 90005)]
SUSPICIOUS_CARDS = [f"{i}" for i in range(9001, 9004)]

ANOMALY_PRONE_CUSTOMER_IDS = [f"cust_{i}" for i in range(80000, 80005)]
ANOMALY_INJECTION_RATE = 0.06
ANOMALY_SPIKE_CHANCE = 0.25

# Cross-border: only CARD and NETBANKING transactions can be foreign-currency
# (UPI/WALLET are India-domestic-only in reality) — a small percentage of
# eligible transactions are cross-border.
CROSS_BORDER_RATE = 0.12
FOREIGN_CURRENCIES = [c for c in SUPPORTED_CURRENCIES if c != "INR"]


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

    roll = random.random()

    if roll < FRAUD_INJECTION_RATE:
        customer_id = random.choice(SUSPICIOUS_CUSTOMER_IDS)
        method = "CARD"
        card_suffix = random.choice(SUSPICIOUS_CARDS)
        amount = round(random.uniform(50000, 100000), 2)
        synthetic_ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 120))
        currency = "INR"

    elif roll < FRAUD_INJECTION_RATE + ANOMALY_INJECTION_RATE:
        customer_id = random.choice(ANOMALY_PRONE_CUSTOMER_IDS)
        card_suffix = fake.credit_card_number()[-4:] if method == "CARD" else None
        is_spike = random.random() < ANOMALY_SPIKE_CHANCE
        amount = round(random.uniform(40000, 90000), 2) if is_spike else round(random.uniform(200, 2000), 2)
        synthetic_ts = generate_synthetic_timestamp()
        currency = "INR"

    else:
        customer_id = f"cust_{random.randint(10000, 99999)}"
        card_suffix = fake.credit_card_number()[-4:] if method == "CARD" else None
        synthetic_ts = generate_synthetic_timestamp()

        # Cross-border eligibility: only CARD/NETBANKING, and only the
        # CROSS_BORDER_RATE slice of those
        is_cross_border = method in ("CARD", "NETBANKING") and random.random() < CROSS_BORDER_RATE

        if is_cross_border:
            currency = random.choice(FOREIGN_CURRENCIES)
            # Foreign-currency amounts are naturally smaller numbers than INR
            amount = round(random.uniform(10, 500), 2)
        else:
            currency = "INR"
            if random.random() < 0.85:
                amount = round(random.uniform(100, 5000), 2)
            else:
                amount = round(random.uniform(5000, 100000), 2)

    return {
        "transaction_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "merchant_id": f"merch_{random.randint(1000, 1050)}",
        "merchant_name": random.choice(MERCHANT_POOL),
        "customer_id": customer_id,
        "amount": amount,
        "currency": currency,
        "method": method,
        "card_last4": card_suffix,
        "created_at": synthetic_ts.isoformat(),
    }
