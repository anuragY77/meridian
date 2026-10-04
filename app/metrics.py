"""
Central Prometheus metric definitions, shared across all Meridian
services. Keeping definitions in one module (rather than each service
defining its own) avoids metric-name collisions and keeps the full set
of exposed metrics discoverable in one place.
"""
from prometheus_client import Counter, Histogram, Gauge

# --- Transaction processing ---
transactions_processed_total = Counter(
    "meridian_transactions_processed_total",
    "Total transactions processed, by final status",
    ["status"],  # success, failed
)

gateway_attempts_total = Counter(
    "meridian_gateway_attempts_total",
    "Total gateway attempts, by gateway and outcome",
    ["gateway_id", "outcome"],  # outcome: success, failure
)

routing_decision_latency_seconds = Histogram(
    "meridian_routing_decision_latency_seconds",
    "Time taken to choose a gateway for one attempt",
    ["strategy"],  # ml, rule
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

# --- Fraud engine ---
fraud_flags_total = Counter(
    "meridian_fraud_flags_total",
    "Total fraud flags raised, by rule",
    ["rule"],
)

# --- Settlement ---
settlements_processed_total = Counter(
    "meridian_settlements_processed_total",
    "Total cross-border settlements processed, by currency",
    ["currency"],
)

reconciliation_mismatches_total = Counter(
    "meridian_reconciliation_mismatches_total",
    "Total settlement reconciliation mismatches detected",
)

# --- Disputes ---
disputes_raised_total = Counter(
    "meridian_disputes_raised_total",
    "Total disputes raised",
)

disputes_resolved_total = Counter(
    "meridian_disputes_resolved_total",
    "Total disputes resolved, by whether it was a false positive",
    ["was_false_positive"],  # "true", "false", "not_applicable"
)

sla_breaches_total = Counter(
    "meridian_sla_breaches_total",
    "Total disputes that breached their SLA deadline",
)

# --- Live gauges (current state, not cumulative) ---
open_disputes_gauge = Gauge(
    "meridian_open_disputes",
    "Current number of open (unresolved) disputes",
)
