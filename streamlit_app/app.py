# streamlit_app/app.py
import os
import time
import threading
from typing import Optional

import streamlit as st
import plotly.express as px
from streamlit.components.v1 import html

from components import (
    apply_neon_style,
    wallet_card,
    neon_button,
    input_card,
    small_tag,
    neon_hash_pill,
    animated_status,
)
import streamlit as st
import json
import traceback
from typing import Callable, Any, Optional, Dict

# Simple CSS injector for neon look (idempotent)
_NEON_INJECTED = "_neon_css_injected"
def apply_neon_style():
    if st.session_state.get(_NEON_INJECTED):
        return
    st.markdown(
        """
        <style>
        .neon-header { font-size:28px; font-weight:800; color: #fff; margin-bottom:6px; }
        .neon-sub { color: #cfeefb; opacity:0.85; font-size:13px; margin-bottom:12px; }
        .neon-card { background: linear-gradient(135deg,#0f0f1f 0%, rgba(255,255,255,0.03) 100%);
                     border-radius:12px; padding:14px; box-shadow: 0 6px 18px rgba(0,0,0,0.6); }
        .neon-pill { background: rgba(255,255,255,0.03); padding:6px 10px; border-radius:999px; font-family:monospace; color:#0ff; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_NEON_INJECTED] = True

# Compact header that fits neon theme
def neon_header(title: str, subtitle: Optional[str] = None):
    apply_neon_style()
    st.markdown(f"<div class='neon-header'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='neon-sub'>{subtitle}</div>", unsafe_allow_html=True)

# Friendly toasts (Streamlit doesn't have native toast; use these wrappers)
def toast_success(msg: str):
    # small green banner + console log
    st.success(msg)

def toast_error(msg: str):
    st.error(msg)

# Safe API wrapper — returns dict; on error returns {"_error": "..."} so UI can check
def safe_api_call(fn: Callable[..., Any], *args, timeout: Optional[float] = None, **kwargs) -> Dict:
    """
    Call an API helper (api_get/api_post). Returns parsed JSON (dict/list) or
    a dict with '_error' key on failure.
    Usage: data = safe_api_call(api_get, "/list_wallets", timeout=3)
    """
    try:
        # allow both (fn returns requests.Response or already-parsed JSON)
        result = fn(*args, **kwargs) if timeout is None else fn(*args, timeout=timeout, **kwargs)

        # If the API helpers already return parsed JSON, just forward it
        if isinstance(result, (dict, list)):
            return result
        # If it's a Response-like object, try to parse JSON
        try:
            return result.json()
        except Exception:
            # fallback: if string, try json.loads, else wrap
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except Exception:
                    return {"_error": f"Unexpected string response: {result[:200]}"}
            return {"_error": "Unexpected API response type"}
    except Exception as e:
        # include traceback for local debugging (but short)
        tb = traceback.format_exc(limit=1)
        return {"_error": f"{e} | {tb.splitlines()[-1]}"}
    
from api import api_get, api_post, BACKEND_URL

st.markdown("""
<style>

body {
    background: #06060f;
}

/* Glow animation */
@keyframes neonPulse {
  0% { box-shadow: 0 0 4px #ff00ff66, 0 0 8px #00eaff66; }
  50% { box-shadow: 0 0 10px #ff00ffcc, 0 0 20px #00eaffcc; }
  100% { box-shadow: 0 0 4px #ff00ff66, 0 0 8px #00eaff66; }
}

/* Neon cards */
.neon-card {
    border-radius: 14px;
    padding: 16px;
    background: rgba(20, 20, 40, 0.6);
    border: 1px solid #ff00ff33;
    backdrop-filter: blur(10px);
    animation: neonPulse 3s infinite;
    transition: transform 0.15s ease;
}

.neon-card:hover {
    transform: translateY(-3px) scale(1.02);
}

/* Headers */
.neon-header {
    font-size: 28px;
    font-weight: 800;
    background: linear-gradient(90deg, #ff00ff, #00eaff);
    -webkit-background-clip: text;
    color: transparent;
    margin-bottom: 6px;
}

.sub-header {
    color: #aaa;
    font-size: 15px;
    margin-bottom: 18px;
}

/* Neon buttons */
.neon-btn {
    padding: 12px 20px;
    background-color: #111;
    border: 1px solid #00eaff;
    color: #00eaff;
    border-radius: 10px;
    font-weight: 700;
    cursor: pointer;
    transition: 0.2s;
}

.neon-btn:hover {
    background-color: #00eaff;
    color: black;
}

</style>
""", unsafe_allow_html=True)


st.set_page_config(
    page_title="Mini-CBDC Stack — Neon UI",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_neon_style()  # inject CSS

st.sidebar.markdown(
    "<h2 style='margin-bottom:4px'>Mini-CBDC Stack</h2><div style='opacity:.7'>Neon demo UI</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")
st.sidebar.write(f"Backend: `{os.environ.get('BACKEND_URL', BACKEND_URL)}`")
st.sidebar.markdown("---")
if st.sidebar.button("Run Auto-Demo"):
    st.session_state["auto_demo"] = True

tabs = st.tabs(
    [
        "🏦 Wallets",
        "💸 Transfer",
        "🪙 Minting",
        "🔗 Explorer",
        "📊 Graph & Insights",
        "🤖 Auto Demo",
    ]
)


# -----------------------
# Wallets Tab (Neon v2)
# -----------------------
with tabs[0]:
    neon_header("Wallets", "Create and manage CBDC wallets")

    # Fetch wallets safely
    wallets = safe_api_call(api_get, "/list_wallets")
    if "_error" in wallets:
        st.warning("Backend offline or unreachable.")
        wallets = []

    # --- Create Wallet Form ---
    st.markdown("<div class='neon-card'>", unsafe_allow_html=True)
    st.markdown("### Create Wallet")
    new_user = st.text_input("User")
    new_currency = st.selectbox("Currency", ["INR-CBDC"], key="create_wallet_currency")
    if st.button("Create Wallet", type="primary"):
        r = safe_api_call(api_post, "/create_wallet",
                          params={"user": new_user, "currency": new_currency})
        if "_error" in r:
            toast_error(r["_error"])
        else:
            toast_success("Wallet created successfully!")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")

    # --- Display Wallets ---
    if isinstance(wallets, list):
        cols = st.columns(3)
        for i, w in enumerate(wallets):
            user = w.get("user", "").upper()
            bals = w.get("balances", {})
            bal_str = "<br>".join([f"<span style='color:#0ff'>{k}</span> : ₹{v}" for k, v in bals.items()])

            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div class='neon-card'>
                        <div style='font-size:20px;font-weight:800;color:#fff'>{user}</div>
                        <div style='margin-top:8px;color:#ccc'>{bal_str}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
# -----------------------
# Transfer Tab
# -----------------------
# -----------------------
# Transfer Tab (Neon v2)
# -----------------------
with tabs[1]:
    neon_header("Transfer", "Move CBDC between wallets")

    st.markdown("<div class='neon-card'>", unsafe_allow_html=True)

    from_user = st.text_input("From User")
    to_user = st.text_input("To User")
    amount = st.number_input("Amount (INR)", min_value=0.0, value=100.0)
    currency = st.selectbox("Currency", ["INR-CBDC"], key="transfer_currency")
    confirm = st.checkbox("Force transfer (duplicate override)")

    if st.button("Send Transfer", type="primary"):
        r = safe_api_call(
            api_post,
            "/transfer",
            params={
                "from_user": from_user,
                "to_user": to_user,
                "amount": amount,
                "currency": currency,
                "confirm": str(confirm).lower()
            },
            timeout=6,
        )

        if "_error" in r:
            toast_error(r["_error"])
        else:
            toast_success("Transfer successful!")

            # show blockchain hash if available
            bh = r.get("blockchain_hash")
            if bh:
                st.markdown(
                    f"<div style='color:#0ff;font-family:monospace;margin-top:10px'>🔗 Hash: {bh}</div>",
                    unsafe_allow_html=True
                )

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------
# Minting Tab
# -----------------------
with tabs[2]:
    st.markdown("## Minting (admin)")
    user = st.text_input("Credit user", value="john", key="m_user")
    amount = st.number_input("Amount to mint", min_value=0.0, value=500.0, step=1.0, key="m_amount")
    currency = st.text_input("Currency", value="INR-CBDC", key="m_currency")
    superkey = st.text_input("Admin Superkey (env ADMIN_KEY)", type="password", key="m_key")
    confirm = st.checkbox("Confirm duplicate mints", value=False, key="m_confirm")

    if neon_button("Mint", key="mint_btn"):
        headers = {"x-superkey": superkey}
        try:
            resp = api_post(
                "/mint",
                params={"user": user, "amount": amount, "currency": currency, "confirm": str(confirm).lower()},
                headers=headers,
                timeout=6,
            )
            st.success("Minted")
            if resp.get("blockchain_hash"):
                st.markdown(neon_hash_pill(resp["blockchain_hash"]))
        except Exception as e:
            st.error(f"Mint failed: {e}")


# -----------------------
# Blockchain Explorer Tab
# -----------------------
with tabs[3]:
    st.markdown("## Blockchain Explorer")
    st.markdown("Recent transactions (audit hashes).")
    try:
        txs = api_get("/list_transactions", timeout=3)
    except Exception:
        txs = []

    for tx in txs:
        st.markdown(
            f"""
            <div class="neon-tx">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div><b>{tx.get('from')}</b> → <b>{tx.get('to')}</b> <span style='opacity:.7'>({tx.get('currency')})</span></div>
                <div>{neon_hash_pill(tx.get('blockchain_hash') or 'pending')}</div>
              </div>
              <div style="opacity:.7;font-size:13px">{tx.get('timestamp')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# -----------------------
# Graph & Insights Tab
# -----------------------
with tabs[4]:
    st.markdown("## Graph & Insights")
    st.markdown("Risk heatmap / transaction volume (placeholder)")
    # dummy chart using plotly
    df = px.data.iris()  # small included dataset as placeholder
    fig = px.scatter(df, x="sepal_width", y="sepal_length", color="species", title="Mock Insights")
    fig.update_layout(template=None, plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


# -----------------------
# Auto Demo Tab
# -----------------------
with tabs[5]:
    st.markdown("## Auto Demo")
    if "auto_demo" not in st.session_state:
        st.session_state["auto_demo"] = False

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.write("Auto-demo shows a slow-motion everyday flow.")
        if neon_button("Start Auto-Demo", key="start_auto"):
            st.session_state["auto_demo"] = True
    with col_b:
        if st.session_state["auto_demo"]:
            if neon_button("Stop Auto-Demo", key="stop_auto"):
                st.session_state["auto_demo"] = False

    if st.session_state["auto_demo"]:
        animated_status("Starting demo...")
        # run demo steps in background thread to avoid blocking
        def demo_runner():
            steps = [
                ("create_wallet", {"user": "demo_john", "currency": "INR-CBDC"}),
                ("mint", {"user": "demo_john", "amount": 500, "currency": "INR-CBDC"}),
                ("transfer", {"from_user": "demo_john", "to_user": "demo_alice", "amount": 100, "currency": "INR-CBDC"}),
            ]
            for step, params in steps:
                animated_status(f"Running: {step}")
                try:
                    if step == "create_wallet":
                        api_post("/create_wallet", params=params, timeout=4)
                    elif step == "mint":
                        api_post("/mint", params=params, headers={"x-superkey": os.environ.get("ADMIN_KEY", "")}, timeout=6)
                    elif step == "transfer":
                        api_post("/transfer", params=params, timeout=6)
                except Exception as e:
                    animated_status(f"Step {step} failed: {e}")
                time.sleep(1.2)
            animated_status("Auto-demo finished.")
            st.session_state["auto_demo"] = False

        threading.Thread(target=demo_runner, daemon=True).start()
        st.info("Auto-demo running in background (check backend logs).")


# Footer
st.markdown("---")
st.markdown("<div style='text-align:center;opacity:.7'>Mini-CBDC Stack • Neon demo UI</div>", unsafe_allow_html=True)


refresh = st.sidebar.checkbox("Auto-refresh", value=False)

