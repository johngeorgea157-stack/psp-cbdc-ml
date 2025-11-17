import os
import sqlite3
import csv
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "psp.db")

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "compliance_logs")

from collections import defaultdict, deque

_rate_limits = defaultdict(lambda: deque())


def get_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    return conn


def log_compliance(from_wallet, to_wallet, amount, currency, tx_type, risk="normal"):
    os.makedirs(LOG_DIR, exist_ok=True)

    # Ensure risk is in readable format
    if isinstance(risk, dict):
        risk_level = risk.get("risk_level", "unknown")
        risk_flags = ", ".join(risk.get("risk_flags", []))
    else:
        risk_level = str(risk)
        risk_flags = ""

    # --- 1️⃣ CSV structured log ---
    csv_file = os.path.join(LOG_DIR, f"transactions_{datetime.now().date()}.csv")
    csv_exists = os.path.isfile(csv_file)
    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not csv_exists:
            writer.writerow(
                [
                    "from_wallet",
                    "to_wallet",
                    "amount",
                    "currency",
                    "timestamp",
                    "type",
                    "risk_level",
                    "risk_flags",
                ]
            )
        writer.writerow(
            [
                from_wallet,
                to_wallet,
                amount,
                currency,
                datetime.now().isoformat(),
                tx_type,
                risk_level,
                risk_flags,
            ]
        )

    # --- 2️⃣ Human-readable daily log ---
    txt_file = os.path.join(LOG_DIR, f"compliance_{datetime.now().date()}.log")
    with open(txt_file, "a") as f:
        f.write(
            f"[{datetime.now().isoformat()}] "
            f"{tx_type.upper()} | {from_wallet} → {to_wallet} | "
            f"₹{amount} {currency} | Risk: {risk_level} ({risk_flags})\n"
        )


from collections import defaultdict

_rate_limits = defaultdict(lambda: deque())  # ip -> deque of timestamps
