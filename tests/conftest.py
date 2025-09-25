import os, sys
import sqlite3
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app, DB_PATH


# ✅ use the real ADMIN_KEY (already set in your environment)
REAL_ADMIN_KEY = os.environ["ADMIN_KEY"]

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "psp.db")

@pytest.fixture(autouse=True)
def reset_db():
    """Reset DB before each test so tests don't interfere with each other"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wallets")
    cursor.execute("DELETE FROM transactions")
    conn.commit()
    conn.close()
    yield

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def admin_key():
    return REAL_ADMIN_KEY