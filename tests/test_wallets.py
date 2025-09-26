from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_create_wallet():
    resp = client.post("/create_wallet?user=testuser&currency=INR-CBDC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"] == "testuser"
    assert data["currency"] == "INR-CBDC"

def test_list_wallets():
    resp = client.get("/list_wallets")
    assert resp.status_code == 200
    wallets = resp.json()
    assert isinstance(wallets, list)