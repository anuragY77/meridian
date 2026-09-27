# app/fx_rates.py
"""
Simulates FX (foreign exchange) rates for cross-border settlement.
Real payment aggregators source live rates from providers (or their own
treasury desk); here we simulate small realistic fluctuations around a
base rate, which is enough to exercise the settlement/reconciliation
logic meaningfully without needing a live FX API.
"""
import random

# Base rates: 1 unit of foreign currency = X INR (approximate, for simulation)
BASE_RATES_TO_INR = {
    "USD": 83.50,
    "EUR": 90.20,
    "GBP": 105.75,
    "AED": 22.75,
}

CONVERSION_FEE_PCT = 0.02   # 2% cross-border conversion fee, typical for payment aggregators

SUPPORTED_CURRENCIES = list(BASE_RATES_TO_INR.keys()) + ["INR"]


def get_fx_rate(currency: str) -> float:
    """
    Returns current INR-equivalent rate for 1 unit of `currency`,
    with small random fluctuation (+/- 0.3%) to simulate real market movement.
    INR itself always returns 1.0 (no conversion needed).
    """
    if currency == "INR":
        return 1.0

    base = BASE_RATES_TO_INR.get(currency)
    if base is None:
        raise ValueError(f"Unsupported currency: {currency}")

    fluctuation = random.uniform(-0.003, 0.003)
    return round(base * (1 + fluctuation), 4)


def convert_to_inr(amount: float, currency: str) -> dict:
    """
    Converts a foreign-currency amount to INR, applying the conversion fee.
    Returns a full breakdown — this breakdown is what gets stored in the
    settlement record, so every rupee is traceable back to its inputs.
    """
    rate = get_fx_rate(currency)
    gross_inr = round(amount * rate, 2)
    fee_inr = round(gross_inr * CONVERSION_FEE_PCT, 2)
    net_inr = round(gross_inr - fee_inr, 2)

    return {
        "original_amount": amount,
        "original_currency": currency,
        "fx_rate_used": rate,
        "gross_inr": gross_inr,
        "conversion_fee_inr": fee_inr,
        "net_settlement_inr": net_inr,
    }
