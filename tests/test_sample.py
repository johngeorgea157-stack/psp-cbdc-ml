import os
def test_create_wallet(client):
    resp = client.post("/create_wallet?user=John&currency=INR-CBDC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"] == "john"

def test_transfer_and_mint(client, admin_key):
    client.post("/create_wallet?user=John&currency=INR-CBDC")
    client.post("/create_wallet?user=Alice&currency=INR-CBDC")

    mint_resp = client.post(
    "/mint?user=John&amount=500&currency=INR-CBDC",
    headers={"x-superkey": os.environ["ADMIN_KEY"]}
  )
    assert mint_resp.status_code == 200

    transfer_resp = client.post(
        "/transfer?from_user=John&to_user=Alice&amount=200&currency=INR-CBDC"
    )
    assert transfer_resp.status_code == 200
    data = transfer_resp.json()
    assert data["status"] == "success"
    assert data["amount"] == 200