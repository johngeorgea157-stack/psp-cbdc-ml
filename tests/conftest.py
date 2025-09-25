import os, sys
import sqlite3
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app, DB_PATH


# ✅ Ensure DB schema exists before tests
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    with open(os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql"), "r") as f:
        cursor.executescript(f.read())
    conn.commit()
    conn.close()

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create tables if not exist at the start of the test session"""
    init_db()

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

def admin_key():
    return os.environ.get("ADMIN_KEY")