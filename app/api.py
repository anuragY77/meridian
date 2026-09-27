# app/api.py
"""
FastAPI backend serving aggregated stats for the Meridian dashboard.
Run with: uvicorn app.api:app --reload --port 8000
"""
import json
from datetime import datetime, timedelta

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from app.database import SessionLocal, Transaction
from app.gateways import GATEWAYS

app = FastAPI(title="Meridian Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/overview")
def get_overview():
    """High-level KPI cards: total transactions, overall success rate, avg latency."""
    db = SessionLocal()
    try:
        total = db.query(func.count(Transaction.transaction_id)).scalar() or 0
        successes = db.query(func.count(Transaction.transaction_id)).filter(
            Transaction.status == "success"
        ).scalar() or 0
        avg_latency = db.query(func.avg(Transaction.last_latency_ms)).filter(
            Transaction.last_latency_ms.isnot(None)
        ).scalar() or 0
        avg_attempts = db.query(func.avg(Transaction.attempt_count)).scalar() or 0

        return {
            "total_transactions": total,
            "success_rate": round(successes / total, 4) if total else 0,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_attempts": round(avg_attempts, 2),
        }
    finally:
        db.close()


@app.get("/api/by-method")
def get_by_method():
    """Success rate breakdown per payment method."""
    db = SessionLocal()
    try:
        # SQLAlchemy doesn't cast booleans portably across DBs cleanly here,
        # so compute success counts with a simpler filtered approach instead:
        result = []
        methods = db.query(Transaction.method).distinct().all()
        for (method,) in methods:
            total = db.query(func.count(Transaction.transaction_id)).filter(
                Transaction.method == method
            ).scalar() or 0
            success = db.query(func.count(Transaction.transaction_id)).filter(
                Transaction.method == method, Transaction.status == "success"
            ).scalar() or 0
            result.append({
                "method": method,
                "total": total,
                "success_rate": round(success / total, 4) if total else 0,
            })
        return sorted(result, key=lambda r: r["total"], reverse=True)
    finally:
        db.close()


@app.get("/api/by-gateway")
def get_by_gateway():
    """
    Success rate + latency per gateway, computed from EVERY attempt
    recorded in attempts_log (not just chosen_gateway_id, which only
    reflects the gateway of a transaction's final SUCCESSFUL attempt
    and silently excludes every failed attempt from the stats).
    """
    db = SessionLocal()
    try:
        transactions = db.query(Transaction).filter(
            Transaction.attempts_log.isnot(None)
        ).all()

        stats: dict[str, dict] = {}

        for txn in transactions:
            try:
                attempts = json.loads(txn.attempts_log)
            except (json.JSONDecodeError, TypeError):
                continue

            for attempt in attempts:
                gw_id = attempt["gateway_id"]
                if gw_id not in stats:
                    stats[gw_id] = {"total": 0, "success": 0, "latency_sum": 0}

                stats[gw_id]["total"] += 1
                if attempt["success"]:
                    stats[gw_id]["success"] += 1
                stats[gw_id]["latency_sum"] += attempt.get("latency_ms", 0)

        result = []
        for gw_id, s in stats.items():
            gw_name = GATEWAYS[gw_id].name if gw_id in GATEWAYS else gw_id
            result.append({
                "gateway_id": gw_id,
                "gateway_name": gw_name,
                "total": s["total"],
                "success_rate": round(s["success"] / s["total"], 4) if s["total"] else 0,
                "avg_latency_ms": round(s["latency_sum"] / s["total"], 1) if s["total"] else 0,
            })

        return sorted(result, key=lambda r: r["total"], reverse=True)
    finally:
        db.close()


@app.get("/api/decline-codes")
def get_decline_codes():
    """Breakdown of failure reasons across all failed attempts."""
    db = SessionLocal()
    try:
        rows = db.query(
            Transaction.last_decline_code,
            func.count(Transaction.transaction_id)
        ).filter(
            Transaction.last_decline_code.isnot(None)
        ).group_by(Transaction.last_decline_code).all()

        total = sum(count for _, count in rows) or 1
        return [
            {"decline_code": code, "count": count, "percentage": round(100 * count / total, 1)}
            for code, count in sorted(rows, key=lambda r: r[1], reverse=True)
        ]
    finally:
        db.close()


@app.get("/api/routing-comparison")
def get_routing_comparison():
    """
    Compares ML-routed vs rule-routed transactions' actual success rates —
    this is the live-dashboard equivalent of the offline backtest from Phase 3.
    """
    db = SessionLocal()
    try:
        result = []
        for strategy in ["ml", "rule"]:
            total = db.query(func.count(Transaction.transaction_id)).filter(
                Transaction.routing_strategy == strategy
            ).scalar() or 0
            success = db.query(func.count(Transaction.transaction_id)).filter(
                Transaction.routing_strategy == strategy, Transaction.status == "success"
            ).scalar() or 0
            avg_attempts = db.query(func.avg(Transaction.attempt_count)).filter(
                Transaction.routing_strategy == strategy
            ).scalar() or 0

            result.append({
                "strategy": strategy,
                "total": total,
                "success_rate": round(success / total, 4) if total else 0,
                "avg_attempts": round(avg_attempts, 2) if total else 0,
            })
        return result
    finally:
        db.close()


@app.get("/api/recent-transactions")
def get_recent_transactions(limit: int = Query(default=20, le=100)):
    """Latest N transactions for a live-feed table."""
    db = SessionLocal()
    try:
        rows = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(limit).all()
        return [
            {
                "transaction_id": r.transaction_id[:8],
                "merchant_name": r.merchant_name,
                "method": r.method,
                "amount": r.amount,
                "status": r.status,
                "chosen_gateway_id": r.chosen_gateway_id,
                "attempt_count": r.attempt_count,
                "routing_strategy": r.routing_strategy,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    finally:
        db.close()
