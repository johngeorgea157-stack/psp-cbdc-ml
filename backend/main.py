from fastapi import FastAPI, Query, HTTPException
from fastapi import Header
import sqlite3
import os
import json
from backend.utils import get_db, log_compliance
import joblib
import pandas as pd
from blockchain.ledger import log_cbdc_transfer
import numpy as np
from backend.models.transactions import load_transactions
from backend.ml.scoring import composite_score
from backend.ml.patterns import detect_patterns
from backend.graph.insights import compute_graph_insights
from backend.graph.insights import router as insights_router

from fastapi.responses import HTMLResponse

app = FastAPI()
DB_PATH = os.path.join(os.path.dirname(__file__), "psp.db")

XAI_EXPLANATIONS = {
    "ml_anomaly": "⚠️ ML model detected an anomalous transaction pattern.",
    "rapid_reuse": "🔁 High-frequency wallet reuse detected in a short time window.",
    "cross_border": "🌍 Transaction resembles a cross-border CBDC flow.",
    "cross_currency": "💱 Cross-currency token movement detected (non-INR-CBDC).",
    "high_value": "💸 Transaction amount exceeds typical thresholds.",
    "suspicious_pair": "🧩 Sender/receiver combination is historically unusual.",
}

app.include_router(insights_router)

def compliance_grade(score):
    """
    Convert risk score (0–1) into A/B/C/D grade.
    Higher score = more risky.
    """
    if score < 0.15:
        return "A"
    if score < 0.35:
        return "B"
    if score < 0.55:
        return "C"
    return "D"


@app.get("/graph_insights")
def graph_insights():
    df = load_transactions(200)
    return compute_graph_insights(df)


@app.get("/pattern_insights")
def pattern_insights():
    df = load_transactions(200)
    return {"patterns": detect_patterns(df)}


@app.get("/composite_risk")
def composite_risk_api(user: str):
    # compute composite risk for the user's latest outgoing tx
    df = load_transactions(200)
    last_tx = df[df["from_wallet"] == user].head(1)
    if last_tx.empty:
        return {"message": "No data for user"}

    conn = get_db()
    try:
        score = composite_score(
            sender=last_tx["from_wallet"].values[0],
            amount=float(last_tx["amount"].values[0]),
            currency=last_tx["currency"].values[0],
            conn=conn,
        )
    finally:
        conn.close()

    return {"user": user, "composite_risk": score}


@app.on_event("startup")
def load_model():
    model_path = "ml/anomaly_model.pkl"
    if os.path.exists(model_path):
        app.state.ml_model = joblib.load(model_path)
        print("✅ ML model loaded")
    else:
        app.state.ml_model = None
        print("⚠️ No ML model found, risk scoring disabled")


def score_transaction(sender, receiver, amount, currency, tx_type, conn):
    """
    Hybrid ML + Rule-based + Clustering-based risk scoring.

    Returns:
        {
            "risk_level": "normal|warning|alert",
            "risk_flags": [...]
        }
    """

    flags = []

    # ------------------------------
    # 1. Cross-currency CBDC detection
    # ------------------------------
    if currency != "INR-CBDC":
        flags.append("cross_currency")

    # ------------------------------
    # 2. High-value threshold
    # ------------------------------
    if amount > 1_000_000:
        flags.append("high_value")

    # ------------------------------
    # 3. Velocity check (multiple transfers in 30 seconds)
    # ------------------------------
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM transactions
        WHERE from_wallet=? AND timestamp > datetime('now', '-30 seconds')
    """,
        (sender,),
    )
    recent = cursor.fetchone()[0]
    if recent > 3:
        flags.append("rapid_reuse")

    # ------------------------------
    # 4. Quirky ML anomaly (placeholder)
    # ------------------------------
    if amount % 777 == 0:
        flags.append("ml_anomaly")

    # ------------------------------
    # 5. Unsupervised ML clustering outlier detection
    # ------------------------------
    try:
        labels, outliers = cluster_transactions(conn)
        # newest transaction = first row in SELECT query, index 0
        if outliers and 0 in outliers:
            flags.append("cluster_outlier")
    except Exception as e:
        # Never break system if clustering fails
        print("[CLUSTERING ERROR]", e)

    # ------------------------------
    # 6. No flags → normal
    # ------------------------------
    if not flags:
        return {"risk_level": "normal", "risk_flags": []}

    # ------------------------------
    # 7. Risk level classification
    # ------------------------------
    if "ml_anomaly" in flags or "cluster_outlier" in flags or "high_value" in flags:
        level = "alert"
    else:
        level = "warning"

    return {"risk_level": level, "risk_flags": flags}


@app.get("/")
def root():
    return {"message": "PSP + CBDC + AI/ML Project Running 🚀"}


# --- create_wallet endpoint (replace existing) ---
@app.post("/create_wallet")
def create_wallet(
    user: str = Query(..., description="Wallet owner"),
    currency: str = Query(..., description="Currency, e.g. INR-CBDC"),
):
    user = user.strip().lower()
    currency = currency.strip().upper()

    with sqlite3.connect(DB_PATH, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ensure uniqueness (user,currency)
        cur.execute(
            "SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency)
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Wallet already exists")

        cur.execute(
            "INSERT INTO wallets (user, currency, balance) VALUES (?, ?, ?)",
            (user, currency, 0.0),
        )
        conn.commit()

    return {"status": "created", "user": user, "currency": currency, "balance": 0.0}


# --- list_wallets endpoint (replace existing) ---
@app.get("/list_wallets")
def list_wallets():
    """
    Return all wallets grouped by user:
    [
      {"user": "john", "balances": {"INR-CBDC": 400.0, "USD-Token": 10.0}},
      ...
    ]
    """
    with sqlite3.connect(DB_PATH, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT user, currency, balance FROM wallets ORDER BY user, currency")
        rows = cur.fetchall()

    out = {}
    for r in rows:
        u = r["user"]
        out.setdefault(u, {})[r["currency"]] = float(r["balance"] or 0.0)

    # convert to list of dicts (same as historical response shape)
    result = [{"user": user, "balances": balances} for user, balances in out.items()]
    return result

from datetime import datetime, timedelta


@app.post("/transfer")
def transfer(
    from_user: str = Query(..., description="Sender wallet owner"),
    to_user: str = Query(..., description="Receiver wallet owner"),
    amount: float = Query(..., description="Amount to transfer"),
    currency: str = Query(..., description="Currency type, e.g. INR-CBDC or USD-Token"),
    confirm: bool = Query(
        False, description="Set to True to confirm duplicate-like transactions"
    ),
):
    from_user = from_user.strip().lower()
    to_user = to_user.strip().lower()

    # ✔ FIX: context manager + timeout protects against DB locks
    with sqlite3.connect(DB_PATH, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            conn.execute("BEGIN IMMEDIATE;")  # atomic lock

            # 1. sender exists + balance
            cursor.execute(
                "SELECT id, balance FROM wallets WHERE user=? AND currency=?",
                (from_user, currency),
            )
            sender = cursor.fetchone()
            if not sender:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Sender wallet not found")
            if sender["balance"] < amount:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Insufficient balance")

            # 2. receiver exists
            cursor.execute(
                "SELECT id FROM wallets WHERE user=? AND currency=?",
                (to_user, currency),
            )
            receiver = cursor.fetchone()
            if not receiver:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Receiver wallet not found")

            # 3. duplicate detection
            timestamp = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT INTO transactions (
                    from_wallet, to_wallet, amount, currency,
                    timestamp, type, blockchain_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (from_user, to_user, amount, currency, timestamp, "transfer", None),
            )

            last_tx = cursor.fetchone()
            if last_tx:
                ts = last_tx["timestamp"]
                if not ts:
                    last_time = datetime.utcnow() - timedelta(hours=1)   # treat as old tx
                else:
                    last_time = datetime.fromisoformat(ts)
                if (
                    datetime.utcnow() - last_time < timedelta(seconds=30)
                    and not confirm
                ):
                    conn.rollback()
                    return {
                        "status": "warning",
                        "message": "This looks like a duplicate transfer in the last 30s. Confirm again to proceed.",
                        "duplicate": True,
                    }

            # 4. update balances
            cursor.execute(
                "UPDATE wallets SET balance=balance-? WHERE id=?",
                (amount, sender["id"]),
            )
            cursor.execute(
                "UPDATE wallets SET balance=balance+? WHERE id=?",
                (amount, receiver["id"]),
            )

            # 5. internal log
            cursor.execute(
                """
                INSERT INTO transactions (from_wallet, to_wallet, amount, currency, type, blockchain_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (from_user, to_user, amount, currency, "transfer", None),
            )

            tx_id = cursor.lastrowid

            # 6. risk scoring
            risk = score_transaction(
                from_user, to_user, amount, currency, "transfer", conn
            )
            flags = risk.get("risk_flags", [])
            explanation = explain_risk_details(amount, currency, flags)
            log_compliance(from_user, to_user, amount, currency, "transfer", risk)

            # 7. blockchain logging
            hash_ = log_cbdc_transfer(
                tx_id=tx_id,
                sender=from_user,
                receiver=to_user,
                amount=amount,
                risk_score=risk,
            )

            cursor.execute(
                "UPDATE transactions SET blockchain_hash=? WHERE id=?", (hash_, tx_id)
            )

            conn.commit()

            return {
                "status": "success",
                "risk": risk,
                "from": from_user,
                "to": to_user,
                "amount": amount,
                "currency": currency,
                "blockchain_hash": hash_,
                "explanation": explanation,
            }

        except Exception as e:
            conn.rollback()
            raise e


@app.post("/mint")
def mint(
    user: str = Query(..., description="Wallet owner to credit"),
    amount: float = Query(..., description="Amount to mint (testing only)"),
    currency: str = Query(..., description="Currency, e.g. INR-CBDC"),
    x_superkey: str = Header(..., description="Superkey for authorization"),
    confirm: bool = Query(
        False, description="Set to True to confirm duplicate-like minting"
    ),
):
    user = user.strip().lower()
    admin_key = get_admin_key()

    if not admin_key:
        raise HTTPException(
            status_code=503, detail="Admin key not configured on server"
        )

    if x_superkey != admin_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # ✔ FIX: context manager + timeout prevents 'database is locked'
    with sqlite3.connect(DB_PATH, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # wallet exists?
        cursor.execute(
            "SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency)
        )
        wallet = cursor.fetchone()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        # duplicate detection
        cursor.execute(
            """
            SELECT timestamp FROM transactions
            WHERE to_wallet=? AND amount=? AND currency=? AND type='mint'
            ORDER BY timestamp DESC LIMIT 1
        """,
            (user, amount, currency),
        )

        last_tx = cursor.fetchone()
        if last_tx:
            ts = last_tx["timestamp"]
            if not ts:
                last_time = datetime.utcnow() - timedelta(hours=1)   # treat as old tx
            else:
                last_time = datetime.fromisoformat(ts)
            if datetime.utcnow() - last_time < timedelta(seconds=30) and not confirm:
                return {
                    "status": "warning",
                    "message": "This looks like a duplicate minting in the last 30s. Confirm again to proceed.",
                    "duplicate": True,
                }

        # update balance
        cursor.execute(
            "UPDATE wallets SET balance=balance+? WHERE id=?", (amount, wallet["id"])
        )

        # log tx internally
        timestamp = datetime.utcnow().isoformat()

        cursor.execute(
            """
            INSERT INTO transactions (
                from_wallet, to_wallet, amount, currency,
                timestamp, type, blockchain_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("CENTRAL_BANK", user, amount, currency, timestamp, "mint", None),
        )

        tx_id = cursor.lastrowid

        # ML scoring
        risk = score_transaction("CENTRAL_BANK", user, amount, currency, "mint", conn)
        flags = risk.get("risk_flags", [])
        explanation = explain_risk_details(amount, currency, flags)
        log_compliance("CENTRAL_BANK", user, amount, currency, "mint", risk)

        # blockchain logging
        hash_ = log_cbdc_transfer(
            tx_id=tx_id,
            sender="CENTRAL_BANK",
            receiver=user,
            amount=amount,
            risk_score=risk,
        )
        cursor.execute(
            "UPDATE transactions SET blockchain_hash=? WHERE id=?", (hash_, tx_id)
        )

        conn.commit()

        return {
            "status": "minted",
            "user": user,
            "amount": amount,
            "currency": currency,
            "risk": risk,
            "blockchain_hash": hash_,
            "explanation": explanation,
        }


@app.get("/list_transactions")
def list_transactions(user: str = None):
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT from_wallet, to_wallet, amount, currency, timestamp, type, blockchain_hash
        FROM transactions
    """
    if user:
        query += " WHERE from_wallet=? OR to_wallet=? ORDER BY timestamp DESC"
        cursor.execute(query, (user, user))
    else:
        query += " ORDER BY timestamp DESC"
        cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "from": r[0],
            "to": r[1],
            "amount": r[2],
            "currency": r[3],
            "timestamp": r[4],
            "type": r[5],
            "blockchain_hash": r[6],
        }
        for r in rows
    ]


@app.post("/fund_wallet")
def fund_wallet(
    user: str = Query(...), amount: float = Query(...), currency: str = Query(...)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency)
    )
    wallet = cursor.fetchone()
    if not wallet:
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found")
    cursor.execute(
        "UPDATE wallets SET balance = balance + ? WHERE id=?", (amount, wallet[0])
    )
    conn.commit()
    conn.close()
    return {"status": "funded", "user": user, "amount": amount, "currency": currency}


# ADMIN_KEY = os.environ.get("ADMIN_KEY", None)


def get_admin_key():
    """Always read ADMIN_KEY fresh from environment."""
    return os.getenv("ADMIN_KEY")


import csv
from fastapi.responses import StreamingResponse
from io import StringIO


@app.get("/export_transactions")
def export_transactions(user: str = None, format: str = "csv"):
    """
    Export all transactions (CSV or JSON).
    If user is provided, filter by that user.
    """
    conn = get_db()
    cursor = conn.cursor()

    if user:
        user = user.strip().lower()
        cursor.execute(
            """
            SELECT from_wallet, to_wallet, amount, currency, timestamp, type
            FROM transactions
            WHERE from_wallet = ? OR to_wallet = ?
            ORDER BY timestamp DESC
            """,
            (user, user),
        )
    else:
        cursor.execute(
            "SELECT from_wallet, to_wallet, amount, currency, timestamp, type FROM transactions ORDER BY timestamp DESC"
        )

    rows = cursor.fetchall()
    conn.close()

    if format == "json":
        return [
            {
                "from": r[0],
                "to": r[1],
                "amount": r[2],
                "currency": r[3],
                "timestamp": r[4],
                "type": r[5],
            }
            for r in rows
        ]

    # Default: CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["from_wallet", "to_wallet", "amount", "currency", "timestamp", "type"]
    )
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@app.post("/demo_cbdc_flow")
def demo_cbdc_flow():
    """
    Runs the full demo flow programmatically:
    1️⃣ Create wallets
    2️⃣ Mint CBDC
    3️⃣ Transfer funds
    4️⃣ Return all results
    """
    import requests

    base_url = "http://127.0.0.1:8000"
    admin_key = os.environ.get("ADMIN_KEY", None)

    if not admin_key:
        raise HTTPException(status_code=503, detail="Admin key not configured")

    results = {}

    # Step 1: Wallet creation
    results["create_wallets"] = [
        requests.post(f"{base_url}/create_wallet?user=John&currency=INR-CBDC").json(),
        requests.post(f"{base_url}/create_wallet?user=Alice&currency=INR-CBDC").json(),
    ]

    # Step 2: Mint funds
    results["mint"] = requests.post(
        f"{base_url}/mint?user=John&amount=500&currency=INR-CBDC",
        headers={"x-superkey": admin_key},
    ).json()

    # Step 3: Transfer funds
    results["transfer"] = requests.post(
        f"{base_url}/transfer?from_user=John&to_user=Alice&amount=100&currency=INR-CBDC"
    ).json()

    # Step 4: List balances
    results["wallets"] = requests.get(f"{base_url}/list_wallets").json()

    # Step 5: List transactions
    results["transactions"] = requests.get(f"{base_url}/list_transactions").json()[:5]

    return {"message": "✅ CBDC Demo Flow Completed Successfully", "results": results}


import matplotlib

matplotlib.use("Agg")  # headless backend for server environments
import matplotlib.pyplot as plt
import base64
import os


@app.get("/ml_risk_insights")
def ml_risk_insights(limit: int = 10):
    """
    Returns recent ML risk analysis results for the last N transactions.
    Response JSON includes:
      - summary: dictionary of risk counts
      - chart: data:image/png;base64,... (ready to embed)
      - file: server file path for direct download (FileResponse works)
    """
    # 1. Read recent transactions
    conn = get_db()
    try:
        df = pd.read_sql_query(
            "SELECT id, amount, type, risk_score AS risk, timestamp FROM transactions ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(limit,),
        )
    finally:
        conn.close()

    if df.empty:
        return {
            "message": "No transactions found",
            "summary": {},
            "chart": None,
            "file": None,
        }

    # 2. Produce a simple bar chart of risk categories
    summary = df["risk"].fillna("unknown").value_counts().to_dict()

    fig, ax = plt.subplots(figsize=(6, 4))
    # bar chart of counts
    ax.bar(summary.keys(), summary.values())
    ax.set_title("Recent ML Risk Classifications")
    ax.set_xlabel("Risk Category")
    ax.set_ylabel("Count")
    plt.tight_layout()

    # Ensure directory exists
    os.makedirs("db/charts", exist_ok=True)
    chart_path = "db/charts/ml_risk_chart.png"

    # Save to disk (headless-safe)
    plt.savefig(chart_path)
    plt.close(fig)

    # Load file and encode as base64 for embedding
    with open(chart_path, "rb") as f:
        b = f.read()
    img_b64 = base64.b64encode(b).decode("utf-8")
    img_data_uri = f"data:image/png;base64,{img_b64}"

    # Return both summary and embedded chart + file path
    return {"summary": summary, "chart": img_data_uri, "file": chart_path}


def build_feature_vector(amount, currency, tx_type):
    """
    Convert transaction metadata into a numerical feature vector.
    """
    currency_map = {"INR-CBDC": 0, "USD-Token": 1, "EUR-CBDC": 2}
    type_map = {"mint": 0, "transfer": 1}

    return np.array(
        [
            float(amount),
            currency_map.get(currency, 9),  # unseen currencies go to 9
            type_map.get(tx_type, 9),
        ]
    )


from sklearn.cluster import DBSCAN


def cluster_transactions(conn, eps=0.5, min_samples=3):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT amount, currency, type
        FROM transactions
        ORDER BY timestamp DESC LIMIT 200
    """)
    rows = cursor.fetchall()

    if len(rows) < 3:
        return None, []

    # Convert to feature vectors
    X = np.array([build_feature_vector(a, c, t) for (a, c, t) in rows])

    # Fit DBSCAN
    model = DBSCAN(eps=eps, min_samples=min_samples).fit(X)

    labels = model.labels_
    outliers = np.where(labels == -1)[0].tolist()

    return labels.tolist(), outliers


@app.get("/clustering_insights")
def clustering_insights(limit: int = 200):
    """
    Returns DBSCAN clustering analysis for recent transactions.
    """
    conn = get_db()
    try:
        labels, outliers = cluster_transactions(conn)
    finally:
        conn.close()

    # cluster summary
    unique = sorted(set(labels))
    summary = {str(c): labels.count(c) for c in unique}

    return {
        "clusters": summary,
        "outliers": outliers,
        "total_transactions": len(labels),
        "notes": [
            "Cluster -1 = outliers (anomalies)",
            "Outliers correlate with ML and rule-based red flags",
        ],
    }


def explain_risk_details(amount, currency, risk_flags):
    explanation = []

    if "ml_anomaly" in risk_flags:
        explanation.append("⚠️ ML model detected anomalous transaction pattern.")
    if "rapid_reuse" in risk_flags:
        explanation.append("🔁 High-frequency wallet activity detected.")
    if "cross_currency" in risk_flags:
        explanation.append(
            f"💱 {currency} is not a domestic CBDC → cross-currency risk."
        )
    if "high_value" in risk_flags:
        explanation.append("💸 Large value transaction above threshold.")

    # No flags?
    if not risk_flags:
        explanation.append("✅ Transaction appears normal under current ML thresholds.")

    # Compute grade
    risk_score = sum("alert" in f for f in risk_flags) / max(1, len(risk_flags))
    explanation.append(f"🧩 Compliance grade: {compliance_grade(risk_score)}")

    return explanation


# from datetime import datetime
@app.get("/risk_dashboard")
def risk_dashboard(limit: int = 20):
    """
    Centralized supervisory dashboard for regulators.
    Combines:
      - DB transactions
      - ML scoring
      - Compliance log summaries
    """

    # 1️⃣ Load recent transactions
    conn = get_db()
    df = pd.read_sql_query(
        """
        SELECT id, from_wallet, to_wallet, amount, currency, type, 
               COALESCE(risk_score, 'unknown') AS risk, timestamp
        FROM transactions ORDER BY timestamp DESC LIMIT ?
    """,
        conn,
        params=(limit,),
    )
    conn.close()

    if df.empty:
        return {"message": "No transactions found", "summary": {}, "high_risk": []}

    # 2️⃣ High-level risk counters
    risk_counts = df["risk"].value_counts().to_dict()

    alerts = df[df["risk"] == "alert"]
    anomalies = df[df["risk"] == "anomaly"]
    high_value = df[df["amount"] > 1_00_000]  # ₹1 lakh threshold

    # 3️⃣ Identify high-risk transactions
    high_risk_df = df[
        (df["risk"].isin(["alert", "anomaly"])) | (df["amount"] > 1_00_000)
    ]

    high_risk = high_risk_df.to_dict(orient="records")

    # 4️⃣ Top risky users
    top_risky = (
        df.groupby("from_wallet")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .to_dict()
    )
    df["risk_flags"] = df["risk"].apply(
        lambda r: [r] if isinstance(r, str) else r.get("risk_flags", [])
    )
    df["grade"] = df["risk_flags"].apply(
        lambda f: compliance_grade(sum("alert" in flag for flag in f) / max(1, len(f)))
    )

    # 5️⃣ Response structure for regulators
    return {
        "summary": {
            "total_transactions": int(df.shape[0]),
            "risk_counts": risk_counts,
            "high_value_count": int(high_value.shape[0]),
            "alert_count": int(alerts.shape[0]),
            "ml_anomaly_count": int(anomalies.shape[0]),
        },
        "top_risky_users": top_risky,
        "high_risk_transactions": high_risk,
    }


LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "compliance_logs")

from pathlib import Path

CHARTS_DIR = Path("db/charts")
LOGS_DIR = Path("logs")
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
COMPLIANCE_LOG = LOGS_DIR / "compliance_events.log"


# --- Helper: Compliance logger ---
def log_compliance_event(from_user, to_user, amount, currency, risk_flags):
    """Append critical compliance events to logs/compliance_events.log"""
    if any(flag in ["alert", "ml_anomaly"] for flag in risk_flags):
        with open(COMPLIANCE_LOG, "a") as log:
            log.write(
                f"[{datetime.utcnow().isoformat()}] ALERT: {from_user} → {to_user} "
                f"{amount} {currency} {risk_flags}\n"
            )


# --- Helper: Compliance grading ---
def compliance_grade(score: float) -> str:
    if score < 0.2:
        return "A"
    elif score < 0.5:
        return "B"
    elif score < 0.7:
        return "C"
    else:
        return "D"


# --- Endpoint 1: /compliance_summary ---
@app.get("/compliance_summary")
def compliance_summary(days: int = 3):
    """
    Summarize compliance logs from the last N days.
    - Reads CSV logs in db/compliance_logs
    - Aggregates risk categories
    - Produces regulator-grade summary
    """
    log_dir = LOG_DIR
    os.makedirs(log_dir, exist_ok=True)

    summaries = []
    cutoff_date = datetime.now().date() - timedelta(days=days)

    # Scan all CSV log files
    for fname in os.listdir(log_dir):
        if not fname.startswith("transactions_") or not fname.endswith(".csv"):
            continue

        # Extract date from filename
        try:
            file_date = datetime.strptime(
                fname.replace("transactions_", "").replace(".csv", ""), "%Y-%m-%d"
            ).date()
        except:
            continue

        # Skip old logs
        if file_date < cutoff_date:
            continue

        # Read CSV
        df = pd.read_csv(os.path.join(log_dir, fname))

        if "risk" not in df.columns:
            continue

        summaries.append(df)

    if not summaries:
        return {
            "message": "No recent compliance logs found",
            "total_transactions": 0,
            "alerts": 0,
            "normal": 0,
            "risk_breakdown": {},
        }

    # Combine all logs
    df_all = pd.concat(summaries, ignore_index=True)

    # Normal vs alerts
    alerts = df_all[df_all["risk"] != "normal"]
    normal = df_all[df_all["risk"] == "normal"]

    # Parse risk flags for breakdown
    breakdown = {}

    for entry in df_all["risk"]:
        # Risk may be a string OR a dictionary-like string from ML output
        if isinstance(entry, str):
            # If it's JSON inside a string
            if entry.startswith("{") and "risk_flags" in entry:
                try:
                    entry = eval(entry)
                except:
                    pass

        if isinstance(entry, dict) and "risk_flags" in entry:
            for flag in entry["risk_flags"]:
                breakdown[flag] = breakdown.get(flag, 0) + 1

    return {
        "total_transactions": len(df_all),
        "alerts": len(alerts),
        "normal": len(normal),
        "risk_breakdown": breakdown,
    }


@app.get("/regulator_risk_feed")
def regulator_risk_feed(days: int = 3):
    """
    Regulator-grade early-warning risk feed.
    Combines:
      - Compliance logs (CSV)
      - ML risk flags
      - Frequency patterns
    Produces:
      - High-risk entities
      - Repeat offenders
      - Flag-weighted severity ranking
    """
    log_dir = LOG_DIR
    os.makedirs(log_dir, exist_ok=True)

    cutoff = datetime.now().date() - timedelta(days=days)
    frames = []

    # Read CSV logs
    for fname in os.listdir(log_dir):
        if fname.startswith("transactions_") and fname.endswith(".csv"):
            d = fname.replace("transactions_", "").replace(".csv", "")
            try:
                file_date = datetime.strptime(d, "%Y-%m-%d").date()
            except:
                continue

            if file_date >= cutoff:
                frames.append(pd.read_csv(os.path.join(log_dir, fname)))

    if not frames:
        return {"message": "No logs available for risk feed", "days_scanned": days}

    df = pd.concat(frames, ignore_index=True)

    # Normalize risk
    def extract_flags(r):
        if isinstance(r, str) and r.startswith("{") and "risk_flags" in r:
            try:
                return eval(r).get("risk_flags", [])
            except:
                return []
        if isinstance(r, dict):
            return r.get("risk_flags", [])
        return []  # normal

    df["flags"] = df["risk"].apply(extract_flags)

    # Severity weight system
    WEIGHTS = {
        "ml_anomaly": 3,
        "cross_border": 4,
        "rapid_reuse": 2,
        "high_value": 2,
        "unknown_flag": 1,
    }

    def compute_score(flags):
        if not flags:
            return 0
        return sum(WEIGHTS.get(f, 1) for f in flags)

    df["severity"] = df["flags"].apply(compute_score)

    # Aggregate per entity
    entity_stats = (
        df.groupby("to_wallet")
        .agg(
            tx_count=("to_wallet", "count"),
            alerts=("severity", lambda x: (x > 0).sum()),
            total_severity=("severity", "sum"),
            flags=("flags", lambda x: [f for lst in x for f in lst]),
        )
        .reset_index()
    )

    # Sort by severity
    entity_stats = entity_stats.sort_values(by="total_severity", ascending=False)

    # Format output
    results = []
    for _, row in entity_stats.iterrows():
        results.append(
            {
                "entity": row["to_wallet"],
                "total_tx": int(row["tx_count"]),
                "alerts": int(row["alerts"]),
                "risk_score": int(row["total_severity"]),
                "top_flags": list(set(row["flags"])),
                "risk_level": (
                    "critical"
                    if row["total_severity"] >= 12
                    else "high"
                    if row["total_severity"] >= 6
                    else "medium"
                    if row["total_severity"] >= 2
                    else "low"
                ),
            }
        )

    return {
        "days_scanned": days,
        "high_risk_entities": results[:10],  # top 10 entities
        "raw_count": len(df),
    }


from backend.ml.features import compute_features
from backend.ml.scoring import weighted_score
from backend.ml.scoring import score_transaction


@app.get("/ml_score/{tx_id}")
def ml_score(tx_id: int):
    """
    Composite ML + Graph + Rule-based risk for a given transaction.
    Returns:
      - features
      - rule_based_risk
      - final_score (0-100)
      - explanation
    """

    # ----------------------
    # 1. Compute or load features
    # ----------------------
    features = compute_features(tx_id)
    if features is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # ----------------------
    # 2. Rule-based risk
    # ----------------------
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT from_wallet, to_wallet, amount, currency, type FROM transactions WHERE id=?",
        (tx_id,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No such transaction")

    sender, receiver, amount, currency, tx_type = row

    rule = score_transaction(
        sender, receiver, amount, currency, tx_type, sqlite3.connect(DB_PATH)
    )

    # ----------------------
    # 3. Weighted ML score
    # ----------------------
    graph_score = features["graph_risk_score"]
    rule_level = rule["risk_level"]

    final_score = weighted_score(features, rule_level, graph_score)

    # ----------------------
    # 4. Explainability
    # ----------------------
    expl = []

    if features["is_cross_currency"]:
        expl.append("🌍 Cross-currency risk identified.")

    if features["velocity_30s"] > 2:
        expl.append("⚡ High short-term velocity.")

    if graph_score > 0.3:
        expl.append("🕸️ Graph centrality risk detected.")

    if rule_level == "alert":
        expl.append("🚨 Rule-based model classified this as ALERT.")
    elif rule_level == "warning":
        expl.append("⚠️ Rule-based warnings triggered.")

    if not expl:
        expl.append("✅ No significant red flags detected.")

    # ----------------------
    # 5. Return all data
    # ----------------------
    return {
        "tx_id": tx_id,
        "features": features,
        "rule_based_risk": rule,
        "final_score": final_score,
        "explanation": expl,
    }


# --- Endpoint 2: /risk_dashboard ---
@app.get("/risk_dashboard")
def risk_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT to_wallet, COUNT(*),
               SUM(risk_score >= 0.7),
               SUM(risk_score BETWEEN 0.4 AND 0.7),
               SUM(risk_score < 0.4),
               MAX(timestamp)
        FROM transactions
        GROUP BY to_wallet
    """)
    rows = cursor.fetchall()

    csv_path = CHARTS_DIR / "risk_dashboard.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["User", "Total Tx", "High", "Medium", "Low", "Last Activity"])
        for r in rows:
            writer.writerow(r)

    # --- Optional visualization ---
    users = [r[0] for r in rows]
    high = [r[2] for r in rows]
    med = [r[3] for r in rows]
    low = [r[4] for r in rows]

    plt.figure(figsize=(8, 4))
    plt.bar(users, high, label="High", alpha=0.8)
    plt.bar(users, med, bottom=high, label="Medium", alpha=0.8)
    plt.bar(
        users, low, bottom=[h + m for h, m in zip(high, med)], label="Low", alpha=0.8
    )
    plt.legend()
    plt.title("Per-User Risk Breakdown")
    plt.xlabel("User")
    plt.ylabel("Transaction Count")

    dashboard_chart = CHARTS_DIR / "risk_dashboard.png"
    plt.savefig(dashboard_chart)
    plt.close()

    return {
        "csv": str(csv_path),
        "chart": str(dashboard_chart),
        "last_updated": datetime.utcnow().isoformat(),
    }


@app.get("/features/{tx_id}")
def get_features(tx_id: int):
    """
    Returns engineered ML features for a given transaction.
    If features are not yet computed, compute them on-demand.
    """

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if exists in feature store
    row = cur.execute(
        """
        SELECT tx_id, amount, is_cross_currency, velocity_30s,
               sender_centrality, receiver_centrality,
               rolling_avg_amount, graph_risk_score, label
        FROM features WHERE tx_id=?
    """,
        (tx_id,),
    ).fetchone()
    conn.close()

    if row:
        # Already exists → return
        return {
            "tx_id": row[0],
            "amount": row[1],
            "is_cross_currency": row[2],
            "velocity_30s": row[3],
            "sender_centrality": row[4],
            "receiver_centrality": row[5],
            "rolling_avg_amount": row[6],
            "graph_risk_score": row[7],
            "label": row[8],
        }

    # Not found → compute now
    feat = compute_features(tx_id)
    if feat is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return feat


def explain_risk(tx):
    """Return explainable text about risk factors for a transaction."""
    risk_flags = tx.get("risk_flags", [])
    explanation = []

    # --- Flag-based reasoning ---
    if "ml_anomaly" in risk_flags:
        explanation.append("⚠️ ML model detected anomalous transaction pattern.")
    if "rapid_reuse" in risk_flags:
        explanation.append("🔁 High-frequency wallet reuse detected.")
    if "cross_border" in risk_flags:
        explanation.append("🌍 Cross-border CBDC transfer identified.")
    if "high_value" in risk_flags:
        explanation.append("💰 Large transaction amount exceeding median value.")
    if "alert" in risk_flags:
        explanation.append("🚨 Compliance alert triggered for review.")
    if not risk_flags:
        explanation.append("✅ Transaction appears normal under current ML thresholds.")

    # --- Compute compliance grade ---
    try:
        alert_score = sum("alert" in r or "ml_anomaly" in r for r in risk_flags) / max(
            1, len(risk_flags)
        )
    except Exception:
        alert_score = 0

    grade = compliance_grade(alert_score)
    explanation.append(f"🧩 Compliance grade: {grade}")

    return explanation


@app.get("/compliance_summary")
def compliance_summary():
    """
    Summarize all transactions by risk level and type.
    Returns:
      - total_tx
      - by_type counts
      - risk_summary counts
      - last_updated
    """
    conn = get_db()
    try:
        df = pd.read_sql_query("SELECT type, risk_score FROM transactions", conn)
    finally:
        conn.close()

    if df.empty:
        return {"message": "No transactions yet"}

    summary = {
        "total_tx": len(df),
        "by_type": df["type"].value_counts().to_dict(),
        "risk_summary": df["risk_score"].fillna("unknown").value_counts().to_dict(),
        "last_updated": datetime.utcnow().isoformat(),
    }
    return summary


@app.get("/compliance_dashboard")
def compliance_dashboard():
    """
    Generates a compliance chart of risk categories over transaction types.
    Returns both PNG (base64) and file path.
    """
    conn = get_db()
    try:
        df = pd.read_sql_query("SELECT type, risk_score FROM transactions", conn)
    finally:
        conn.close()

    if df.empty:
        return {"message": "No data to visualize"}

    pivot = df.pivot_table(
        index="type", columns="risk_score", aggfunc=len, fill_value=0
    )

    # Generate chart
    fig, ax = plt.subplots(figsize=(6, 4))
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_title("Compliance Risk Breakdown by Transaction Type")
    ax.set_xlabel("Transaction Type")
    ax.set_ylabel("Count")
    plt.tight_layout()

    os.makedirs("db/charts", exist_ok=True)
    path = "db/charts/compliance_dashboard.png"
    plt.savefig(path)
    plt.close(fig)

    with open(path, "rb") as f:
        b = f.read()
    b64 = base64.b64encode(b).decode("utf-8")
    uri = f"data:image/png;base64,{b64}"

    return {"chart": uri, "file": path}


@app.get("/explain_risk_report")
def explain_risk_report(limit: int = 20):
    """
    Returns the latest transactions along with ML risk flags
    and human-readable explanations (from explain_risk()).
    """
    conn = get_db()
    try:
        df = pd.read_sql_query(
            "SELECT id, from_wallet, to_wallet, amount, currency, "
            "type, COALESCE(risk_score, 'unknown') AS risk, timestamp "
            "FROM transactions ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(limit,),
        )
    finally:
        conn.close()

    if df.empty:
        return {"message": "No transactions found"}

    out = []
    for _, row in df.iterrows():
        flags = row["risk"]
        if isinstance(flags, str):
            risk_flags = [flags] if flags != "normal" else []
        else:
            risk_flags = flags

        explanation = explain_risk(
            {
                "amount": row["amount"],
                "currency": row["currency"],
                "risk_flags": risk_flags,
            }
        )

        out.append(
            {
                "id": row["id"],
                "from": row["from_wallet"],
                "to": row["to_wallet"],
                "amount": row["amount"],
                "currency": row["currency"],
                "risk_flags": risk_flags,
                "timestamp": row["timestamp"],
                "explanation": explanation,
            }
        )

    return out


def check_rate_limit(key, limit=10, per_seconds=60):
    q = _rate_limits[key]
    now = time.time()
    while q and now - q[0] > per_seconds:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True

# ============================================================
#  GRAPH ENDPOINTS (STABLE MINIMAL VERSION)
# ============================================================
@app.get("/graph/tx_network")
def graph_tx_network():
    """
    Return a minimal transaction network graph:
    - nodes = unique wallet_ids
    - edges = weighted by transaction count
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # nodes
    cur.execute("SELECT DISTINCT user FROM wallets")
    users = [row["user"] for row in cur.fetchall()]

    # edges (from -> to, weight counts)
    cur.execute("""
        SELECT from_wallet, to_wallet, COUNT(*) AS weight
        FROM transactions
        WHERE from_wallet != 'CENTRAL_BANK'
        GROUP BY from_wallet, to_wallet
    """)
    edges = [
        {
            "source": row["from_wallet"],
            "target": row["to_wallet"],
            "weight": row["weight"]
        }
        for row in cur.fetchall()
    ]

    return {
        "nodes": users,
        "edges": edges,
        "count_nodes": len(users),
        "count_edges": len(edges)
    }

@app.get("/welcome", response_class=HTMLResponse)
def welcome_page():
    return """
    <html>
    <head>
        <title>CBDC PSP – Demo</title>
        <style>
            body { font-family: Arial; padding: 20px; line-height: 1.6; }
            h1 { color: #2A6; }
            code { background: #eee; padding: 3px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>CBDC PSP – Hackathon Demo</h1>

        <h2>What is CBDC?</h2>
        <p>CBDC is a digital form of sovereign currency issued by the central bank.
        This project demonstrates a programmable PSP layer on top of CBDC rails.</p>

        <h2>What This System Shows</h2>
        <ul>
            <li>Wallet creation + mint + peer-to-peer transfer</li>
            <li>ML-Scoring (rule-based + composite + graph risk)</li>
            <li>Transaction blockchain hash logging</li>
            <li>Supervisory dashboards (risk, compliance)</li>
            <li>Network graph analysis</li>
        </ul>

        <h2>ML Scoring</h2>
        <p>
            The system uses:
            <ul>
                <li><b>Composite score</b> (backward compatible)</li>
                <li><b>Weighted score</b> (ML + graph + rules)</li>
                <li><b>Risk flags</b> (High velocity, Cross currency, Large value, Unusual pairs)</li>
                <li><b>Compliance grade</b> (A–D)</li>
            </ul>
        </p>

        <h2>Graph Risk Engine</h2>
        <p>
            Builds a network of users and edges (transactions).  
            Detects high-centrality hubs, suspicious clusters, and weighted edges.
        </p>

        <h2>Useful API Endpoints</h2>
        <ul>
            <li><code>/create_wallet</code></li>
            <li><code>/mint</code></li>
            <li><code>/transfer</code></li>
            <li><code>/transactions</code></li>
            <li><code>/graph/tx_network</code></li>
            <li><code>/insights/top_users</code></li>
            <li><code>/ml_summary</code> </li>
        </ul>

        <h2>Run Demo</h2>
        <p>From terminal:</p>
        <code>python run_demo.py</code>

        <p>Made by John George Alexander.</p>
    </body>
    </html>
    """

import base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from backend.ml.scoring import score_transaction
from backend.graph.insights import compute_graph_insights
from backend.ml.features import compute_features


@app.get("/ml_summary")
def ml_summary():
    """
    Summary of last 50 transactions:
    - average risk_score
    - risk distribution
    - top flags
    - base64 chart
    """

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
        SELECT 
            id, amount, risk_score, risk_flags, timestamp
        FROM transactions
        ORDER BY id DESC
        LIMIT 50
        """)

        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {
                "count": 0,
                "average_risk": 0,
                "risk_levels": {},
                "top_flags": [],
                "chart_base64": None,
            }

        import json
        import base64
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        risks = []
        level_counts = {"normal": 0, "warning": 0, "alert": 0}
        flag_counts = {}

        for row in rows:
            _, amount, risk_score, flags_raw, ts = row

            r = float(risk_score) if risk_score is not None else 0.0
            risks.append(r)

            # Parse flags (stored as string)
            try:
                flags = json.loads(flags_raw) if flags_raw else []
            except:
                flags = []

            # Count flags
            for f in flags:
                flag_counts[f] = flag_counts.get(f, 0) + 1

            # Classify risk
            if r < 0.2:
                level_counts["normal"] += 1
            elif r < 0.5:
                level_counts["warning"] += 1
            else:
                level_counts["alert"] += 1

        avg_risk = sum(risks) / len(risks)

        # ---------- Chart ----------
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(risks)
        ax.set_title("Recent Risk Scores")
        ax.set_ylim(0, 1)

        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        chart_b64 = base64.b64encode(buf.read()).decode()

        return {
            "count": len(risks),
            "average_risk": round(avg_risk, 4),
            "risk_levels": level_counts,
            "top_flags": sorted(flag_counts.items(), key=lambda x: x[1], reverse=True),
            "chart_base64": chart_b64,
        }

    except Exception as e:
        return {"error": str(e)}