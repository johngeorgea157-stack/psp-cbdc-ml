# streamlit_app/components.py
import os
import streamlit as st
from uuid import uuid4

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")


def apply_neon_style():
    css = """
    <style>
    :root{
        --bg1: linear-gradient(135deg, #ff3cac, #5620ff 40%, #00f0ff 100%);
    }
    .stApp { 
        background: radial-gradient(circle at 10% 10%, rgba(255,255,255,0.02), transparent),
                    linear-gradient(180deg, rgba(10,10,12,1), rgba(2,2,10,1));
        color: #EDEDF5;
        min-height:100vh;
    }
    .neon-card{
        background: linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        border-radius:18px;
        padding:16px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.6), 0 0 20px rgba(213,0,255,0.06);
        border: 1px solid rgba(255,255,255,0.04);
        margin-bottom:12px;
    }
    .neon-tx{
        background: linear-gradient(90deg, rgba(255,20,147,0.03), rgba(0,255,240,0.02));
        padding:12px;border-radius:12px;margin-bottom:8px;
        border: 1px solid rgba(255,255,255,0.02);
    }
    .neon-btn{
        background: linear-gradient(90deg,#ff2dcb,#7a11ff 60%, #00f0ff);
        color:white;padding:10px 16px;border-radius:12px;border:none;cursor:pointer;font-weight:600;
        box-shadow: 0 4px 18px rgba(122,17,255,0.18);
    }
    .neon-btn:active{ transform: translateY(1px); }
    .neon-hash {
        padding:6px 10px;border-radius:999px;font-family:monospace;
        background: linear-gradient(90deg,#00f0ff,#7a11ff,#ff2dcb); color:black; font-weight:700;
        display:inline-block;
    }
    .muted{ opacity:.7; font-size:13px }
    input, textarea { background: rgba(255,255,255,0.02); color:inherit; border-radius:8px; padding:8px; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def neon_button(label: str, key: str = None):
    key = key or str(uuid4())
    clicked = st.button(label, key=key)
    # simple wrapper to show visually
    if clicked:
        st.markdown(f"<div style='padding:6px 0;'></div>", unsafe_allow_html=True)
    return clicked


def wallet_card(user: str, balances: dict):
    st.markdown(f"<div class='neon-card'><h4 style='margin:0'>{user}</h4>", unsafe_allow_html=True)
    for cur, bal in (balances or {}).items():
        st.markdown(f"<div class='muted'>{cur}: <b style='font-size:18px'>{bal}</b></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def input_card(title="Title", subtitle="subtitle", key=None):
    if key and key not in st.session_state:
        st.session_state[key + "_user"] = ""
        st.session_state[key + "_currency"] = "INR-CBDC"
    st.text_input("User", key=key + "_user")
    st.text_input("Currency", key=key + "_currency")


def small_tag(text: str):
    return f"<span style='padding:4px 8px;border-radius:999px;background:rgba(255,255,255,0.03);'>{text}</span>"


def neon_hash_pill(h: str):
    if not h:
        return "<span class='neon-hash'>pending</span>"
    return f"<span class='neon-hash'>{h}</span>"


def animated_status(msg: str):
    st.markdown(f"<div style='padding:8px;border-radius:10px;background:linear-gradient(90deg, rgba(255,20,147,0.06), rgba(0,240,255,0.02));'>{msg}</div>", unsafe_allow_html=True)