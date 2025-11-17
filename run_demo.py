#!/usr/bin/env python3
# run_demo.py — resilient demo client for local FastAPI server

import os
import time
import requests

BASE_URL = os.getenv("DEMO_BASE_URL", "http://127.0.0.1:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "demo_key_please_change")

# Make sure demo and server agree on ADMIN_KEY (useful if server reads it each request)
os.environ["ADMIN_KEY"] = ADMIN_KEY
headers = {"x-superkey": ADMIN_KEY, "Accept": "application/json"}


def wait_for_server(url, timeout=15, interval=0.5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url + "/")
            if r.status_code in (200, 404, 405):
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)
    return False


def safe_post(path, params=None, hdrs=None, json=None):
    url = BASE_URL + path
    try:
        r = requests.post(
            url, params=params, headers=hdrs or headers, json=json, timeout=5
        )
        return r
    except requests.exceptions.RequestException as e:
        return e


def safe_get(path, params=None, hdrs=None):
    url = BASE_URL + path
    try:
        r = requests.get(url, params=params, headers=hdrs or headers, timeout=5)
        return r
    except requests.exceptions.RequestException as e:
        return e


def show_resp(resp):
    if isinstance(resp, requests.Response):
        print("-> HTTP", resp.status_code)
        ctype = resp.headers.get("content-type", "")
        text = resp.text.strip()
        if resp.status_code == 200:
            try:
                print(resp.json())
            except Exception:
                # not-json body, dump first 400 chars
                print("(non-json body)", text[:400])
        else:
            print("(error body)", text[:800])
    else:
        # exception object
        print("-> Request exception:", repr(resp))


def main():
    print("🚀 Starting CBDC Demo Flow")
    print("Base URL:", BASE_URL)
    print("Waiting for server...", end="", flush=True)
    ok = wait_for_server(BASE_URL)
    print(" done" if ok else " FAILED")
    if not ok:
        print(
            "Server did not respond. Start uvicorn backend.main:app --reload and try again."
        )
        return

    # 1. Create wallets (John & Alice)
    print("\n⚙️  Creating wallets...")
    r1 = safe_post("/create_wallet", params={"user": "John", "currency": "INR-CBDC"})
    r2 = safe_post("/create_wallet", params={"user": "Alice", "currency": "INR-CBDC"})
    print("John wallet ->")
    show_resp(r1)
    print("Alice wallet ->")
    show_resp(r2)

    # 2. Mint (must check return code before .json)
    print("\n⚙️  Minting ₹500 for John...")
    r = safe_post(
        "/mint",
        params={"user": "John", "amount": 500, "currency": "INR-CBDC"},
        hdrs=headers,
    )
    if isinstance(r, requests.Response) and r.status_code == 200:
        try:
            data = r.json()
            print("✅ Success:", data)
        except Exception:
            print("✅ Success (non-json):")
            show_resp(r)
    else:
        print("❌ Failed:")
        show_resp(r)

    # 3. Transfer
    print("\n⚙️  Transferring ₹100 from John → Alice...")
    r = safe_post(
        "/transfer",
        params={
            "from_user": "John",
            "to_user": "Alice",
            "amount": 100,
            "currency": "INR-CBDC",
        },
    )
    if isinstance(r, requests.Response) and r.status_code == 200:
        try:
            print("✅ Success:", r.json())
        except Exception:
            print("✅ Success (non-json):")
            show_resp(r)
    else:
        print("❌ Failed:")
        show_resp(r)

    # 4. Show wallets + recent txs
    print("\n📊 Final Wallet Balances:")
    r = safe_get("/list_wallets")
    show_resp(r)

    print("\n🔗 Recent Transactions (showing blockchain_hash):")
    r = safe_get("/list_transactions", params={"limit": 10})
    show_resp(r)

    print("\n🏁 Demo complete!")


if __name__ == "__main__":
    main()
