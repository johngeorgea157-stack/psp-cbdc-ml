from fastapi import FastAPI, Query, HTTPException
from fastapi import Header
import sqlite3
import os
from backend.utils import get_db, log_compliance
from sklearn.ensemble import IsolationForest
import joblib
import pandas as pd
from blockchain.ledger import log_cbdc_transfer

app = FastAPI()
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "psp.db")

@app.on_event("startup")
def load_model():
    model_path = "ml/anomaly_model.pkl"
    if os.path.exists(model_path):
        app.state.ml_model = joblib.load(model_path)
        print("✅ ML model loaded")
    else:
        app.state.ml_model = None
        print("⚠️ No ML model found, risk scoring disabled")

def score_transaction(from_wallet, to_wallet, amount, currency, tx_type, conn):
    """
    Hybrid risk scoring:
    - Rule-based duplicate detection
    - ML anomaly scoring
    """
    risk_flags = []

    # 1. Duplicate transaction rule (within 30s)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp FROM transactions
        WHERE from_wallet=? AND to_wallet=? AND amount=? AND currency=? AND type=?
        ORDER BY timestamp DESC LIMIT 1
    """, (from_wallet, to_wallet, amount, currency, tx_type))
    last_tx = cursor.fetchone()

    if last_tx:
        last_time = datetime.fromisoformat(last_tx[0])
        if datetime.now() - last_time < timedelta(seconds=30):
            risk_flags.append("duplicate_within_30s")

    # 2. ML anomaly detection (Isolation Forest or similar)
    try:
        import joblib
        import pandas as pd
        model = joblib.load("ml/anomaly_model.pkl")
        data = pd.DataFrame([{"amount": amount, "currency_code": hash(currency) % 1000}])
        pred = model.predict(data[["amount", "currency_code"]])[0]
        if pred == -1:
            risk_flags.append("ml_anomaly")
    except Exception:
        # if model not available, skip ML
        risk_flags.append("ml_unavailable")

    # Final decision
    if not risk_flags:
        return "normal"
    return ",".join(risk_flags)
@app.get("/")
def root():
    return {"message": "PSP + CBDC + AI/ML Project Running 🚀"}

@app.post("/create_wallet")
def create_wallet(
    user: str = Query(..., description="Name of the wallet owner"),
    currency: str = Query(..., description="Currency type, e.g. INR-CBDC or USD-Token")
):
    user = user.strip().lower()

    conn = get_db()
    cursor = conn.cursor()

    # 🔥 Check if wallet already exists
    cursor.execute("SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Wallet already exists")

    cursor.execute(
        "INSERT INTO wallets (user, currency, balance) VALUES (?, ?, ?)",
        (user, currency, 0)
    )
    conn.commit()
    conn.close()
    return {"status": "wallet created", "user": user, "currency": currency, "balance": 0}

@app.get("/list_wallets")
def list_wallets():
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user, currency, balance FROM wallets")
    rows = cursor.fetchall()
    conn.close()

    wallets = {}
    for user, currency, balance in rows:
        user = user.strip().lower()
        if user not in wallets:
            wallets[user] = {}
        wallets[user][currency] = balance

    return [
        {"user": user, "balances": balances}
        for user, balances in wallets.items()
    ]
from datetime import datetime, timedelta

@app.post("/transfer")
def transfer(
    from_user: str = Query(..., description="Sender wallet owner"),
    to_user: str = Query(..., description="Receiver wallet owner"),
    amount: float = Query(..., description="Amount to transfer"),
    currency: str = Query(..., description="Currency type, e.g. INR-CBDC or USD-Token"),
    confirm: bool = Query(False, description="Set to True to confirm duplicate-like transactions")
):  
    from_user = from_user.strip().lower()
    to_user = to_user.strip().lower()
    conn = get_db()
    cursor = conn.cursor()

    # 🧩 1. Check sender balance
    cursor.execute("SELECT id, balance FROM wallets WHERE user=? AND currency=?", (from_user, currency))
    sender = cursor.fetchone()
    if not sender:
        conn.close()
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    if sender[1] < amount:
        conn.close()
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 🧩 2. Check receiver wallet
    cursor.execute("SELECT id FROM wallets WHERE user=? AND currency=?", (to_user, currency))
    receiver = cursor.fetchone()
    if not receiver:
        conn.close()
        raise HTTPException(status_code=404, detail="Receiver wallet not found")

    # 🧩 3. Duplicate transaction check (last 30 sec, same from/to/amount/currency)
    cursor.execute("""
        SELECT timestamp FROM transactions
        WHERE from_wallet=? AND to_wallet=? AND amount=? AND currency=? AND type='transfer'
        ORDER BY timestamp DESC LIMIT 1
    """, (from_user, to_user, amount, currency))
    last_tx = cursor.fetchone()

    if last_tx:
        last_time = datetime.fromisoformat(last_tx[0])
        if datetime.utcnow() - last_time < timedelta(seconds=30) and not confirm:
            conn.close()
            return {
                "status": "warning",
                "message": "This looks like a duplicate transfer in the last 30s. Confirm again to proceed.",
                "duplicate": True
            }

    # 🧩 4. Update balances
    cursor.execute("UPDATE wallets SET balance = balance - ? WHERE id=?", (amount, sender[0]))
    cursor.execute("UPDATE wallets SET balance = balance + ? WHERE id=?", (amount, receiver[0]))

    # 🧩 5. Log transaction
    cursor.execute(
        "INSERT INTO transactions (from_wallet, to_wallet, amount, currency, type) VALUES (?, ?, ?, ?, ?)",
        (from_user, to_user, amount, currency, "transfer")
    )

    tx_id = cursor.lastrowid

    # 🧠 6. Run ML risk scoring
    risk = score_transaction(from_user, to_user, amount, currency, "transfer", conn)
    log_compliance(from_user, to_user, amount, currency, "transfer", risk=risk)

    # 🔗 7. Blockchain logging (Polkadot + fallback)
    blockchain_hash = log_cbdc_transfer(
        tx_id=tx_id,
        sender=from_user,
        receiver=to_user,
        amount=amount,
        risk_score=risk
    )
    cursor.execute("UPDATE transactions SET blockchain_hash=? WHERE id=?", (blockchain_hash, tx_id))
    # ✅ 8. Commit to DB
    conn.commit()
    conn.close()

    # 🧾 9. Return full response
    return {
        "status": "success",
        "risk": risk,
        "from": from_user,
        "to": to_user,
        "amount": amount,
        "currency": currency,
        "blockchain_hash": blockchain_hash
    }

from datetime import datetime, timedelta
from fastapi import Header

@app.post("/mint")
def mint(
    user: str = Query(..., description="Wallet owner to credit"),
    amount: float = Query(..., description="Amount to mint (testing only)"),
    currency: str = Query(..., description="Currency, e.g. INR-CBDC"),
    x_superkey: str = Header(..., description="Superkey for authorization"),
    confirm: bool = Query(False, description="Set to True to confirm duplicate-like minting")
):  
    user = user.strip().lower()
    if ADMIN_KEY is None:
        raise HTTPException(status_code=503, detail="Admin key not configured on server")

    # 🔐 Verify admin key
    if x_superkey != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_db()
    cursor = conn.cursor()

    # ✅ Ensure wallet exists
    cursor.execute("SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency))
    wallet = cursor.fetchone()
    if not wallet:
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found")

    # ⚠️ Duplicate minting check (within 30 seconds)
    cursor.execute("""
        SELECT timestamp FROM transactions
        WHERE to_wallet=? AND amount=? AND currency=? AND type='mint'
        ORDER BY timestamp DESC LIMIT 1
    """, (user, amount, currency))
    last_tx = cursor.fetchone()

    if last_tx:
        last_time = datetime.fromisoformat(last_tx[0])
        if datetime.utcnow() - last_time < timedelta(seconds=30) and not confirm:
            conn.close()
            return {
                "status": "warning",
                "message": "This looks like a duplicate minting in the last 30s. Confirm again to proceed.",
                "duplicate": True
            }

    # 💰 Update wallet balance
    cursor.execute("UPDATE wallets SET balance = balance + ? WHERE id=?", (amount, wallet[0]))

    # 🧾 Log the transaction
    cursor.execute(
        "INSERT INTO transactions (from_wallet, to_wallet, amount, currency, type) VALUES (?, ?, ?, ?, ?)",
        ("CENTRAL_BANK", user, amount, currency, "mint")
    )

    tx_id = cursor.lastrowid  # unique transaction ID

    # 🧠 Run risk scoring
    risk = score_transaction("CENTRAL_BANK", user, amount, currency, "mint", conn)
    log_compliance("CENTRAL_BANK", user, amount, currency, "mint", risk)

    # 🔗 Log mint event to Polkadot (or mock hash if unavailable)
    blockchain_hash = log_cbdc_transfer(
        tx_id=tx_id,
        sender="CENTRAL_BANK",
        receiver=user,
        amount=amount,
        risk_score=risk
    )
    cursor.execute("UPDATE transactions SET blockchain_hash=? WHERE id=?", (blockchain_hash, tx_id))
    # ✅ Commit to DB and close connection
    conn.commit()
    conn.close()

    return {
        "status": "minted",
        "user": user,
        "amount": amount,
        "currency": currency,
        "risk": risk,
        "blockchain_hash": blockchain_hash
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
            "blockchain_hash": r[6]
        }
        for r in rows
    ]
@app.post("/fund_wallet")
def fund_wallet(
    user: str = Query(...),
    amount: float = Query(...),
    currency: str = Query(...)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency))
    wallet = cursor.fetchone()
    if not wallet:
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found")
    cursor.execute("UPDATE wallets SET balance = balance + ? WHERE id=?", (amount, wallet[0]))
    conn.commit()
    conn.close()
    return {"status": "funded", "user": user, "amount": amount, "currency": currency}

ADMIN_KEY = os.environ.get("ADMIN_KEY", None)



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
            (user, user)
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
                "type": r[5]
            }
            for r in rows
        ]

    # Default: CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["from_wallet", "to_wallet", "amount", "currency", "timestamp", "type"])
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transactions.csv"})
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
        requests.post(f"{base_url}/create_wallet?user=Alice&currency=INR-CBDC").json()
    ]

    # Step 2: Mint funds
    results["mint"] = requests.post(
        f"{base_url}/mint?user=John&amount=500&currency=INR-CBDC",
        headers={"x-superkey": admin_key}
    ).json()

    # Step 3: Transfer funds
    results["transfer"] = requests.post(
        f"{base_url}/transfer?from_user=John&to_user=Alice&amount=100&currency=INR-CBDC"
    ).json()

    # Step 4: List balances
    results["wallets"] = requests.get(f"{base_url}/list_wallets").json()

    # Step 5: List transactions
    results["transactions"] = requests.get(f"{base_url}/list_transactions").json()[:5]

    return {
        "message": "✅ CBDC Demo Flow Completed Successfully",
        "results": results
    }
from fastapi import HTTPException
from fastapi.responses import FileResponse
import matplotlib
matplotlib.use("Agg")  # headless backend for server environments
import matplotlib.pyplot as plt
import io, base64, os
import pandas as pd

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
            conn, params=(limit,)
        )
    finally:
        conn.close()

    if df.empty:
        return {"message": "No transactions found", "summary": {}, "chart": None, "file": None}

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
    return {
        "summary": summary,
        "chart": img_data_uri,
        "file": chart_path
    }
# from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "compliance_logs")

