import os
import sqlite3
import csv
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "psp.db")
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "compliance_logs")

def get_db():
    return sqlite3.connect(DB_PATH)

def log_compliance(from_wallet, to_wallet, amount, currency, tx_type):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"transactions_{datetime.now().date()}.csv")

    file_exists = os.path.isfile(log_file)
    with open(log_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["from_wallet", "to_wallet", "amount", "currency", "timestamp", "type"])
        writer.writerow([from_wallet, to_wallet, amount, currency, datetime.now().isoformat(), tx_type])