# backend/models/database.py
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "psp.db"))

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    print(f"📌 Initializing DB at {DB_PATH}")

    conn = get_conn()
    c = conn.cursor()

    # Wallets table
    c.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        currency TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0,
        UNIQUE(user, currency)
    );
    """)

    # Transactions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_wallet TEXT,
        to_wallet TEXT,
        amount REAL,
        currency TEXT,
        timestamp TEXT,
        type TEXT,
        blockchain_hash TEXT,
        risk_score REAL,
        risk_flags TEXT
    );
    """)

    # ML Feature store
    c.execute("""
    CREATE TABLE IF NOT EXISTS features (
        tx_id INTEGER PRIMARY KEY,
        amount REAL,
        is_cross_currency INTEGER,
        velocity_30s INTEGER,
        sender_centrality REAL,
        receiver_centrality REAL,
        rolling_avg_amount REAL,
        graph_risk_score REAL,
        label INTEGER DEFAULT NULL
    );
    """)

    conn.commit()
    conn.close()
    print("✔ DB initialized")
