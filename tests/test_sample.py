from fastapi.testclient import TestClient
import os, sqlite3
from backend.main import app, DB_PATH

client = TestClient(app)

def reset_db():
    # Reset database before each test
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS wallets (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, currency TEXT, balance REAL DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, from_wallet TEXT, to_wallet TEXT, amount REAL, currency TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, type TEXT)")
    conn.commit()
    conn.close()

def setup_function():
    reset_db()

def test_create_wallet():
    response = client.post("/create_wallet?user=Alice&currency=INR-CBDC")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "wallet created"

def test_transfer_and_mint():
    # Mint funds to John
    os.environ["ADMIN_KEY"] = "supersecret"
    client.post("/create_wallet?user=John&currency=INR-CBDC")
    client.post("/create_wallet?user=Alice&currency=INR-CBDC")
    mint_resp = client.post("/mint?user=John&amount=500&currency=INR-CBDC&admin_key=supersecret")
    assert mint_resp.status_code == 200

    # Transfer from John to Alice
    transfer_resp = client.post("/transfer?from_user=John&to_user=Alice&amount=200&currency=INR-CBDC")
    assert transfer_resp.status_code == 200
    transfer_data = transfer_resp.json()
    assert transfer_data["status"] == "success"
    assert transfer_data["from"] == "John"
    assert transfer_data["to"] == "Alice"