from fastapi.testclient import TestClient
from backend.main import app
import os

client = TestClient(app)

def test_transfer():
    # ensure wallets exist
    client.post("/create_wallet?user=testuser&currency=INR-CBDC")
    client.post("/create_wallet?user=alice&currency=INR-CBDC")

    # mint some funds
    client.post(
        "/mint?user=testuser&amount=200&currency=INR-CBDC",
        headers={"x-superkey": os.environ["ADMIN_KEY"]}
    )

    resp = client.post(
        "/transfer?from_user=testuser&to_user=alice&amount=100&currency=INR-CBDC"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["amount"] == 100