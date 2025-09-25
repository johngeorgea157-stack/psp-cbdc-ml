from fastapi import FastAPI, Query
import sqlite3
import os

app = FastAPI()
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "psp.db")

def get_db():
    return sqlite3.connect(DB_PATH)

@app.get("/")
def root():
    return {"message": "PSP + CBDC + AI/ML Project Running 🚀"}

@app.post("/create_wallet")
def create_wallet(
    user: str = Query(..., description="Name of the wallet owner"),
    currency: str = Query(..., description="Currency type, e.g. INR-CBDC or USD-Token")
):
    conn = get_db()
    cursor = conn.cursor()
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
    cursor.execute("SELECT id, user, currency, balance FROM wallets")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "user": r[1], "currency": r[2], "balance": r[3]}
        for r in rows
    ]