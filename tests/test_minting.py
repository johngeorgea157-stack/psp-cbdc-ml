from fastapi.testclient import TestClient
from backend.main import app
import os

client = TestClient(app)

def test_mint():
    # create wallet first
    client.post("/create_wallet?user=testuser&currency=INR-CBDC")

    response = client.post(
        "/mint?user=testuser&amount=500&currency=INR-CBDC",
        headers={"x-superkey": os.environ["ADMIN_KEY"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "minted"
    assert data["amount"] == 500