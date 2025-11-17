import os
import sqlite3

# ------------------------------------------------------------------
# SINGLE unified database file — always backend/psp.db
# ------------------------------------------------------------------
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "psp.db"))


def get_conn():
    """Return connection with correct SQLite settings."""
    return sqlite3.connect(
        DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=10,
    )


def init_db():
    """Initialize a clean, correct database schema."""
    print("Initializing database at:", DB_PATH)

    conn = get_conn()
    c = conn.cursor()

    # --------------------------------------------------------------
    # Wallets Table (Final Correct Version)
    # --------------------------------------------------------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        currency TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0,
        UNIQUE(user, currency)
    );
    """)

    # --------------------------------------------------------------
    # Transactions Table (Final Correct Version)
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    # ML Feature Store
    # --------------------------------------------------------------
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
    print("✔ Database initialized successfully.")


if __name__ == "__main__":
    init_db()