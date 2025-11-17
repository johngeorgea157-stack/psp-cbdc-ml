import os
import sys
import sqlite3
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app, DB_PATH

os.environ["PYTEST_ADDOPTS"] = "--dist no"


# ✅ Ensure DB schema exists before tests
def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    cursor = conn.cursor()
    with open(
        os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql"), "r"
    ) as f:
        cursor.executescript(f.read())
    conn.commit()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create tables if not exist at the start of the test session"""
    init_db()


from backend.models.database import init_db, DB_PATH
from backend.main import app
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    """
    FULL DB RESET before each test:
    - Delete the old DB
    - Recreate correct schema
    """

    # 1. Remove existing DB file
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # 2. Recreate schema
    init_db()

    yield



@pytest.fixture
def client():
    return TestClient(app)


def admin_key():
    return os.environ.get("ADMIN_KEY")
