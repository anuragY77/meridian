# Switchboard — Intelligent Payment Routing & Reconciliation Engine

Switchboard simulates a payment-routing layer similar to what a payment
aggregator (like Razorpay) runs in production: incoming transactions are
routed to the payment gateway/bank most likely to succeed, using a machine
learning model trained on historical outcomes — not hardcoded rules.

The name comes from old telephone switchboards, where operators manually
routed calls to the best available line. This system does the same thing
for payments, automatically.

## Why this exists

Payment routing is one of the core engineering problems in fintech infra —
choosing the right gateway/bank for a transaction directly affects success
rate, which directly affects revenue. This project builds a working,
end-to-end version of that problem: simulation → event streaming →
idempotent transaction processing → ML-based routing → live dashboard.

## Architecture

```
Simulator → Redpanda (Kafka-compatible) → Processor → PostgreSQL
   ↓
ML Router (scikit-learn)
   ↓
Redis (idempotency + live gateway health)
   ↓
FastAPI → Next.js Dashboard
```

**Why these choices:**

| Component | Choice | Why |
|---|---|---|
| Event streaming | Redpanda (Kafka-API-compatible) | Gives real Kafka-style event-streaming experience (consumer groups, partitions, offsets) without the ops overhead of a full Kafka cluster — appropriate for a single-developer build |
| Backend | Python + FastAPI | Keeps the ML model and backend in one language, avoiding unnecessary cross-service network calls for a solo build |
| Database | PostgreSQL | ACID guarantees are required for the transaction state machine — idempotency depends on this |
| Idempotency + live health | Redis | Fast key-lookup with TTL is the right tool for duplicate-prevention and for tracking each gateway's rolling recent success rate |
| ML model | RandomForestClassifier (scikit-learn) | Simulated dataset size and the need for calibrated, explainable probabilities didn't justify a deep-learning approach |
| Dashboard | Next.js + Recharts | Polls a FastAPI backend every 5s for live reconciliation stats |

## Core engineering features

- **Idempotency**: every transaction carries an idempotency key; Redis `SETNX`
  atomically prevents duplicate processing (prevents double-charging).
- **Transaction state machine**: `pending → routing → success/failed`,
  persisted in Postgres with a full per-attempt audit log.
- **Retry with exponential backoff**: up to 3 attempts across different
  gateways on failure, backing off 1s → 2s → 4s.
- **Feature-flagged routing**: `ROUTING_STRATEGY=ml|rule` in `.env` switches
  between the trained model and a static rule-based baseline — the same
  pattern real payment companies use for safe rollout/rollback of new
  routing logic.

## The ML routing model

### Feature engineering
- Static: transaction amount, payment method, hour of day, day of week,
  is_night, is_high_value
- **Live**: `recent_success_rate` — each gateway's rolling success rate over
  its last 50 outcomes, tracked in Redis and updated after every real
  attempt. This turned out to be the single most important feature (ahead
  of amount and gateway identity), because it captures real-time gateway
  degradation that no static formula can know in advance.

### Evaluation methodology (and why it matters)

Two mistakes were caught and fixed during development, both worth
documenting because they're the actual point of building an evaluation
pipeline rather than trusting the first metric that comes out:

1. **Random train/test split initially overstated performance.** The first
   split let the model be evaluated on rows it may have effectively already
   seen (via the rolling-history feature). Switching to a **time-based
   split** (train on the earliest 80% of transactions, test only on the
   later 20%) dropped the illusion and produced a trustworthy number:
   **the model picks the true-best gateway 84.9% of the time** on
   completely unseen data.

2. **Per-attempt classification metrics (precision/recall) are the wrong
   lens for a routing problem.** Individual transaction outcomes are
   Bernoulli draws — even a "good" gateway fails some fixed percentage of
   the time by design, so no classifier can predict individual coin-flips
   well. The metric that actually matters is **decision quality**: given a
   transaction, does the model choose a gateway close to the best available
   option? That's what the 84.9% figure measures — not classification
   accuracy on individual attempts.

### Results (held-out, time-based backtest)

| Method | True-best pick rate | Model vs Random | Model vs Rule-based baseline |
|---|---|---|---|
| UPI (3 gateways) | — | +1.49pp | **+0.72pp** |
| CARD (2 gateways) | — | +1.72pp | −0.53pp |
| WALLET (2 gateways) | — | +2.12pp | +0.26pp |
| NETBANKING (1 gateway) | — | 0 (no choice exists) | 0 |
| **Overall** | **84.9%** (1113/1311) | — | — |

**Known limitation, stated honestly**: the model slightly underperforms the
rule-based baseline on CARD transactions. Likely cause: only 2 eligible
gateways means the "true-best gap" is small (higher relative noise), and
the interaction between `is_high_value` and gateway choice is likely not
fully captured by the current feature set (`is_high_value` has the lowest
feature importance of all features used).

**Live A/B comparison caveat**: the dashboard's live ML-vs-rule comparison
uses noisy Bernoulli outcomes on a comparatively small sample (6,511 vs
2,582 transactions), and the observed 0.39pp gap falls within the combined
standard error of the two samples — it is **not** statistically
significant. The offline, deterministic, time-based backtest above is the
primary evidence for routing quality, not the live dashboard number.

## Dashboard

Live reconciliation dashboard built with Next.js, polling a FastAPI backend
every 5 seconds:
- Overall KPIs (transaction volume, success rate, latency, avg attempts)
- Success rate by payment method
- Decline code breakdown
- Per-gateway performance (computed from every logged attempt, not just
  successful ones — an earlier version of this had an aggregation bug that
  made every gateway look like it had 100% success, since it only counted
  `chosen_gateway_id`, which is only ever set on a successful attempt)
- ML vs rule-based routing comparison
- Live transaction feed

## Running it locally

**Prerequisites**: Docker, Python 3.11+, Node.js 18+

```bash
# 1. Clone and configure
git clone https://github.com/anuragY77/switchboard.git
cd switchboard
cp .env.example .env   # then edit POSTGRES_PASSWORD etc.

# 2. Start infrastructure
docker-compose up -d

# 3. Python backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

python -m app.simulator_service    # terminal 1 — generates fake transactions
python -m app.processor_service    # terminal 2 — routes and processes them
python -m app.train_model          # after enough data has accumulated
uvicorn app.api:app --reload --port 8000   # terminal 3 — dashboard API

# 4. Dashboard
cd switchboard-dashboard
npm install
npm run dev   # http://localhost:3000
```

## What I'd build next

- Fraud/anomaly detection module (cross-transaction velocity checks),
  designed to plug onto the existing transaction stream without touching
  the core routing logic
- A larger live A/B sample to make the ML-vs-rule comparison statistically
  significant on its own, not just in the offline backtest
- A feature to better capture the amount × gateway interaction that's
  currently underperforming on CARD transactions
- **ML-routing latency overhead**: the router currently loops over every
  eligible gateway and calls `predict_proba()` once per gateway — at
  production scale this should batch-score all candidate gateways in a
  single model call (plus in-memory model caching), so per-transaction
  routing latency stays flat as the gateway count grows
