import sqlite3
import numpy as np
import networkx as nx
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "psp.db")


# ------------------------------------------------------------
# Helper: load transaction graph
# ------------------------------------------------------------
def build_graph():
    conn = sqlite3.connect(DB_PATH)
    df = conn.execute("""
        SELECT from_wallet, to_wallet FROM transactions
    """).fetchall()
    conn.close()

    G = nx.DiGraph()
    for f, t in df:
        G.add_edge(f, t)
    return G


# ------------------------------------------------------------
# Helper: compute rolling average per user
# ------------------------------------------------------------
def rolling_avg_amount(user, conn):
    rows = conn.execute(
        """
        SELECT amount FROM transactions
        WHERE from_wallet = ?
        ORDER BY timestamp DESC LIMIT 5
    """,
        (user,),
    ).fetchall()

    if not rows:
        return 0.0

    arr = [r[0] for r in rows]
    return float(np.mean(arr))


# ------------------------------------------------------------
# Helper: compute velocity (transactions in last 30 seconds)
# ------------------------------------------------------------
def velocity_30s(sender, conn):
    (count,) = conn.execute(
        """
        SELECT COUNT(*) FROM transactions
        WHERE from_wallet = ?
        AND timestamp > datetime('now', '-30 seconds')
    """,
        (sender,),
    ).fetchone()
    return int(count)


# ------------------------------------------------------------
# Helper: compute graph centrality
# ------------------------------------------------------------
def centrality(graph, node):
    if node not in graph:
        return 0.0
    cent = nx.betweenness_centrality(graph, normalized=True)
    return float(cent.get(node, 0.0))


# ------------------------------------------------------------
# MAIN FUNCTION: compute features for a given transaction
# ------------------------------------------------------------
def compute_features(tx_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT id, from_wallet, to_wallet, amount, currency
        FROM transactions WHERE id=?
    """,
        (tx_id,),
    ).fetchone()

    if not row:
        conn.close()
        return None

    _, sender, receiver, amount, currency = row

    # Build graph only once per call
    G = build_graph()

    # Feature calculations
    is_cross = 1 if currency != "INR-CBDC" else 0
    vel = velocity_30s(sender, conn)
    sender_cent = centrality(G, sender)
    receiver_cent = centrality(G, receiver)
    roll = rolling_avg_amount(sender, conn)

    # Basic graph-derived risk score
    graph_risk = float(
        0.4 * is_cross + 0.3 * (vel / 5) + 0.2 * sender_cent + 0.1 * receiver_cent
    )

    # Insert into the feature store table
    cur.execute(
        """
        INSERT OR REPLACE INTO features
        (tx_id, amount, is_cross_currency, velocity_30s,
         sender_centrality, receiver_centrality,
         rolling_avg_amount, graph_risk_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (tx_id, amount, is_cross, vel, sender_cent, receiver_cent, roll, graph_risk),
    )

    conn.commit()
    conn.close()

    return {
        "tx_id": tx_id,
        "amount": amount,
        "is_cross_currency": is_cross,
        "velocity_30s": vel,
        "sender_centrality": sender_cent,
        "receiver_centrality": receiver_cent,
        "rolling_avg_amount": roll,
        "graph_risk_score": graph_risk,
    }
