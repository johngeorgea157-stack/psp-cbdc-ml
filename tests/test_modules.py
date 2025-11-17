import os
import sqlite3
from fastapi.testclient import TestClient

from backend import main as backend_main
from backend.main import app, DB_PATH

# ------------------------------------------------------
# 🔐 Always set ADMIN_KEY for tests
# ------------------------------------------------------
os.environ["ADMIN_KEY"] = "test_admin_key"
headers = {"x-superkey": os.environ["ADMIN_KEY"]}

client = TestClient(app)


# ------------------------------------------------------
# 🧹 Reset database between tests
# ------------------------------------------------------
def reset_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(wallets)")
    if cur.fetchall():
        cur.execute("DELETE FROM wallets")

    cur.execute("PRAGMA table_info(transactions)")
    if cur.fetchall():
        cur.execute("DELETE FROM transactions")

    conn.commit()
    conn.close()


# ------------------------------------------------------
# 🧩 Stub Polkadot logging for deterministic tests
# ------------------------------------------------------
def stub_ledger(*args, **kwargs):
    return "mockhash123"


backend_main.log_cbdc_transfer = stub_ledger
backend_main.app.state.ml_model = None  # disable ML model


# ------------------------------------------------------
# 🚀 Smoke test: wallet → mint → transfer flow
# ------------------------------------------------------
def test_endpoints_smoke_flow():
    reset_db()

    # Create wallets
    assert (
        client.post("/create_wallet?user=TestUser&currency=INR-CBDC").status_code == 200
    )
    assert (
        client.post("/create_wallet?user=CounterParty&currency=INR-CBDC").status_code
        == 200
    )

    # Mint
    r = client.post(
        "/mint?user=TestUser&amount=1000&currency=INR-CBDC", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "minted"
    assert "blockchain_hash" in data

    # Transfer
    r = client.post(
        "/transfer?from_user=TestUser&to_user=CounterParty&amount=200&currency=INR-CBDC"
    )
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "success"
    assert out["risk"]


# ------------------------------------------------------
# 📊 Graph & Insights endpoints
# ------------------------------------------------------
def test_graph_and_insights_endpoints():
    reset_db()

    client.post("/create_wallet?user=A&currency=INR-CBDC")
    client.post("/create_wallet?user=B&currency=INR-CBDC")

    client.post("/mint?user=A&amount=500&currency=INR-CBDC", headers=headers)
    client.post("/transfer?from_user=A&to_user=B&amount=50&currency=INR-CBDC")

    # Risk chart
    r = client.get("/ml_risk_insights")
    assert r.status_code == 200
    payload = r.json()
    assert "summary" in payload
    assert payload["chart"].startswith("data:image/png;base64,")

    # Dashboard
    r = client.get("/risk_dashboard")
    assert r.status_code == 200
    assert "summary" in r.json()


# ------------------------------------------------------
# 🧠 Composite risk API (optional)
# ------------------------------------------------------
def test_composite_risk_api():
    reset_db()

    payload = {
        "sender": "x",
        "receiver": "y",
        "amount": 1234,
        "currency": "INR-CBDC",
        "tx_type": "transfer",
    }

    r = client.post("/composite_risk", json=payload)

    if r.status_code == 200:
        j = r.json()
        assert "risk_level" in j
        assert "risk_flags" in j
    else:
        assert r.status_code in (404, 405)
