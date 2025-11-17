import sqlite3
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime

from .engine import build_graph, graph_risk
import pandas as pd
import os
DB_PATH = os.path.join(os.path.dirname(__file__), "psp.db")

router = APIRouter()


# -----------------------------
# Existing graph insights
# -----------------------------
def compute_graph_insights(df: pd.DataFrame) -> dict:
    G = build_graph(df)
    risks = {node: graph_risk(G, node) for node in G.nodes}
    hubs = sorted(risks.items(), key=lambda x: x[1], reverse=True)
    return {
        "node_risks": risks,
        "top_hubs": hubs[:8]
    }


# -----------------------------
# NEW: /insights/top_users
# -----------------------------
@router.get("/insights/top_users")
def insights_top_users():
    """
    Returns:
    - velocity_top: users with most transfers in last 30 seconds
    - highest_risk: users whose recent transactions have the most 'alert' or 'warning'
    """

    try:
        conn = sqlite3.connect(DB_PATH, timeout=3)
        cur = conn.cursor()

        # -----------------------------------
        # 1) Top velocity (last 30 seconds)
        # -----------------------------------
        cur.execute(
            """
            SELECT from_wallet, COUNT(*)
            FROM transactions
            WHERE timestamp > datetime('now','-30 seconds')
            GROUP BY from_wallet
            ORDER BY COUNT(*) DESC
            LIMIT 5;
            """
        )

        velocity_top = [
            {"user": row[0], "count_30s": row[1]}
            for row in cur.fetchall()
        ]

        # -----------------------------------
        # 2) Highest risk users (simple rule)
        # We detect risky tx by:
        #   - high amount
        #   - cross currency (if any)
        #   - rapid velocity (>3 in 30s)
        #
        # No risk_logs table required.
        # -----------------------------------
        cur.execute(
            """
            SELECT from_wallet, amount, currency, timestamp
            FROM transactions
            ORDER BY timestamp DESC
            LIMIT 200;
            """
        )

        rows = cur.fetchall()
        risk_accumulator = {}

        for user, amount, currency, ts in rows:
            if user is None:
                continue

            risk = 0

            # high amount
            if amount > 1_000_000:
                risk += 2

            # cross-currency
            if currency != "INR-CBDC":
                risk += 1

            # velocity check
            cur.execute(
                """
                SELECT COUNT(*)
                FROM transactions
                WHERE from_wallet=? AND timestamp > datetime('now','-30 seconds')
                """,
                (user,)
            )
            cnt = cur.fetchone()[0]
            if cnt > 3:
                risk += 2

            risk_accumulator[user] = risk_accumulator.get(user, 0) + risk

        highest_risk = sorted(
            [{"user": u, "risk_score": s} for u, s in risk_accumulator.items()],
            key=lambda x: x["risk_score"],
            reverse=True
        )[:5]

        return JSONResponse(
            {
                "velocity_top": velocity_top,
                "highest_risk": highest_risk,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)