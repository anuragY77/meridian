import random
from datetime import datetime
from dataclasses import dataclass
from typing import Literal

PaymentMethod = Literal["UPI", "CARD", "NETBANKING", "WALLET"]


@dataclass
class Gateway:
    """Represents a simulated payment gateway/PSP/bank in Meridian."""
    id: str
    name: str
    supported_methods: list[PaymentMethod]
    base_success_rate: float  # 0.0 to 1.0
    night_penalty: float = 0.0       # drops during maintenance windows (1-5 AM)
    high_value_penalty: float = 0.0  # stricter checks on large amounts
    high_value_threshold: float = 50000.0
    base_latency_ms: int = 200
    latency_jitter_ms: int = 100


GATEWAYS: dict[str, Gateway] = {
    "hdfc_upi": Gateway(
        id="hdfc_upi", name="HDFC-UPI",
        supported_methods=["UPI"], base_success_rate=0.93,
        night_penalty=0.15, base_latency_ms=180, latency_jitter_ms=80,
    ),
    "icici_card": Gateway(
        id="icici_card", name="ICICI-Card",
        supported_methods=["CARD"], base_success_rate=0.89,
        high_value_penalty=0.20, high_value_threshold=30000.0,
        base_latency_ms=350, latency_jitter_ms=150,
    ),
    "phonepe_upi": Gateway(
        id="phonepe_upi", name="PhonePe-UPI",
        supported_methods=["UPI", "WALLET"], base_success_rate=0.95,
        night_penalty=0.05, base_latency_ms=150, latency_jitter_ms=60,
    ),
    "gpay_upi": Gateway(
        id="gpay_upi", name="GPay-UPI",
        supported_methods=["UPI"], base_success_rate=0.94,
        night_penalty=0.08, base_latency_ms=160, latency_jitter_ms=70,
    ),
    "sbi_netbanking": Gateway(
        id="sbi_netbanking", name="SBI-Netbanking",
        supported_methods=["NETBANKING"], base_success_rate=0.78,
        night_penalty=0.25, base_latency_ms=600, latency_jitter_ms=300,
    ),
    "axis_card": Gateway(
        id="axis_card", name="Axis-Card",
        supported_methods=["CARD"], base_success_rate=0.91,
        high_value_penalty=0.12, high_value_threshold=40000.0,
        base_latency_ms=300, latency_jitter_ms=120,
    ),
    "paytm_wallet": Gateway(
        id="paytm_wallet", name="Paytm-Wallet",
        supported_methods=["WALLET"], base_success_rate=0.90,
        base_latency_ms=140, latency_jitter_ms=50,
    ),
}


def get_gateways_for_method(method: PaymentMethod) -> list[Gateway]:
    return [gw for gw in GATEWAYS.values() if method in gw.supported_methods]


def compute_effective_success_rate(gateway: Gateway, amount: float, timestamp: datetime) -> float:
    rate = gateway.base_success_rate
    hour = timestamp.hour
    if 1 <= hour < 5:
        rate -= gateway.night_penalty
    if amount >= gateway.high_value_threshold:
        rate -= gateway.high_value_penalty
    rate += random.uniform(-0.03, 0.03)
    return max(0.05, min(0.99, rate))


def simulate_gateway_attempt(gateway: Gateway, amount: float, timestamp: datetime) -> dict:
    effective_rate = compute_effective_success_rate(gateway, amount, timestamp)
    success = random.random() < effective_rate
    latency_ms = gateway.base_latency_ms + random.randint(0, gateway.latency_jitter_ms)

    decline_code = None
    if not success:
        decline_code = random.choice([
            "INSUFFICIENT_FUNDS", "ISSUER_TIMEOUT", "BANK_SERVER_DOWN",
            "3DS_FAILED", "RISK_DECLINED", "INVALID_CREDENTIALS",
        ])

    return {
        "gateway_id": gateway.id,
        "gateway_name": gateway.name,
        "success": success,
        "latency_ms": latency_ms,
        "decline_code": decline_code,
        "effective_success_rate_at_attempt": round(effective_rate, 4),
    }


def compute_expected_success_rate(gateway: Gateway, amount: float, timestamp: datetime) -> float:
    """
    Deterministic version of compute_effective_success_rate — NO random
    per-call jitter. Used only as a stable oracle for evaluation, so that
    calling it twice for the same (gateway, amount, timestamp) always
    gives the same answer. The stochastic version stays in use for the
    actual simulator (real-world day-to-day drift is genuinely unknowable
    in advance), but evaluation needs a fixed reference point to compare against.
    """
    rate = gateway.base_success_rate
    hour = timestamp.hour
    if 1 <= hour < 5:
        rate -= gateway.night_penalty
    if amount >= gateway.high_value_threshold:
        rate -= gateway.high_value_penalty
    return max(0.05, min(0.99, rate))