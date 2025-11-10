#!/usr/bin/env python3
"""
CBDC–PSP Demo Runner 🚀
Runs a full flow:
1️⃣ Create wallets (John & Alice)
2️⃣ Mint CBDC to John
3️⃣ Transfer funds from John → Alice
4️⃣ Display final balances and blockchain hashes
"""

import requests
import time

BASE_URL = "http://127.0.0.1:8000"
ADMIN_KEY = "your_real_admin_key_here"  # 🔐 Replace with your actual ADMIN_KEY


def run_step(desc, func):
    print(f"\n⚙️  {desc}...")
    try:
        result = func()
        print("✅ Success:", result)
    except Exception as e:
        print("❌ Failed:", e)


def create_wallets():
    r1 = requests.post(f"{BASE_URL}/create_wallet?user=John&currency=INR-CBDC")
    r2 = requests.post(f"{BASE_URL}/create_wallet?user=Alice&currency=INR-CBDC")
    return [r1.json(), r2.json()]


def mint_funds():
    r = requests.post(
        f"{BASE_URL}/mint?user=John&amount=500&currency=INR-CBDC",
        headers={"x-superkey": ADMIN_KEY}
    )
    return r.json()


def transfer_funds():
    r = requests.post(
        f"{BASE_URL}/transfer?from_user=John&to_user=Alice&amount=100&currency=INR-CBDC"
    )
    return r.json()


def list_wallets():
    r = requests.get(f"{BASE_URL}/list_wallets")
    return r.json()


def list_transactions():
    r = requests.get(f"{BASE_URL}/list_transactions")
    return r.json()


if __name__ == "__main__":
    print("\n🚀 Starting CBDC Demo Flow\n" + "=" * 40)

    run_step("Creating wallets", create_wallets)
    time.sleep(1)

    run_step("Minting ₹500 for John", mint_funds)
    time.sleep(1)

    run_step("Transferring ₹100 from John → Alice", transfer_funds)
    time.sleep(1)

    print("\n📊 Final Wallet Balances:")
    wallets = list_wallets()
    for w in wallets:
        print(f"   💼 {w['user']}: {w['balances']}")

    print("\n🔗 Recent Transactions (showing blockchain_hash):")
    for tx in list_transactions()[:5]:
        print(f"   {tx['from']} → {tx['to']} | ₹{tx['amount']} | hash={tx.get('blockchain_hash', 'N/A')}")

    print("\n🏁 Demo complete!\n")