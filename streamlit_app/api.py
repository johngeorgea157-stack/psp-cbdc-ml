# streamlit_app/api.py
import os
import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")


def api_get(path, timeout=5):
    url = f"{BACKEND_URL}{path}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_post(path, params=None, headers=None, timeout=6):
    params = params or {}
    url = f"{BACKEND_URL}{path}"
    resp = requests.post(url, params=params, headers=headers or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()