from fastapi import FastAPI, Query, HTTPException
from fastapi import Header
import sqlite3
import os
from backend.utils import get_db, log_compliance


app = FastAPI()
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "psp.db")


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

    # 1. Check sender balance
    cursor.execute("SELECT id, balance FROM wallets WHERE user=? AND currency=?", (from_user, currency))
    sender = cursor.fetchone()
    if not sender:
        conn.close()
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    if sender[1] < amount:
        conn.close()
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 2. Check receiver wallet
    cursor.execute("SELECT id FROM wallets WHERE user=? AND currency=?", (to_user, currency))
    receiver = cursor.fetchone()
    if not receiver:
        conn.close()
        raise HTTPException(status_code=404, detail="Receiver wallet not found")

    # 3. Duplicate transaction check (last 30 sec, same from/to/amount/currency)
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

    # 4. Update balances
    cursor.execute("UPDATE wallets SET balance = balance - ? WHERE id=?", (amount, sender[0]))
    cursor.execute("UPDATE wallets SET balance = balance + ? WHERE id=?", (amount, receiver[0]))

    # 5. Log transaction
    cursor.execute(
        "INSERT INTO transactions (from_wallet, to_wallet, amount, currency, type) VALUES (?, ?, ?, ?, ?)",
        (from_user, to_user, amount, currency, "transfer")
    )
    log_compliance(from_user, to_user, amount, currency, "transfer")

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "from": from_user,
        "to": to_user,
        "amount": amount,
        "currency": currency
    }
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


from datetime import datetime, timedelta
from fastapi import Header

@app.post("/mint")
def mint(
    user: str = Query(..., description="Wallet owner to credit"),
    amount: float = Query(..., description="Amount to mint (testing only)"),
    currency: str = Query(..., description="Currency, e.g. INR-CBDC"),
    x_superkey: str = Header(..., description="Superkey for authorization"),  # passed in header
    confirm: bool = Query(False, description="Set to True to confirm duplicate-like minting")
):  
    user = user.strip().lower()
    if ADMIN_KEY is None:
        raise HTTPException(status_code=503, detail="Admin key not configured on server")

    # Verify user-provided key matches the server secret
    if x_superkey != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_db()
    cursor = conn.cursor()

    # Ensure wallet exists
    cursor.execute("SELECT id FROM wallets WHERE user=? AND currency=?", (user, currency))
    wallet = cursor.fetchone()
    if not wallet:
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Duplicate minting check (last 30s, same user/currency/amount)
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

    # Update wallet balance
    cursor.execute("UPDATE wallets SET balance = balance + ? WHERE id=?", (amount, wallet[0]))

    # Log the mint
    cursor.execute(
        "INSERT INTO transactions (from_wallet, to_wallet, amount, currency, type) VALUES (?, ?, ?, ?, ?)",
        ("CENTRAL_BANK", user, amount, currency, "mint")
    )
    log_compliance("CENTRAL_BANK", user, amount, currency, "mint")

    conn.commit()
    conn.close()

    return {"status": "minted", "user": user, "amount": amount, "currency": currency}

@app.get("/list_transactions")
def list_transactions(user: str = None):
    """
    List all transactions. If ?user= is given, filter by that user.
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

from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "compliance_logs")

