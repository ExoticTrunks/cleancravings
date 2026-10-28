import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Each test session gets its own throwaway SQLite DB
# (set TEST_DATABASE_URL to run the suite against Postgres instead, e.g. a local Supabase)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{ROOT / 'tests' / '.test.db'}"
os.environ["DEV_AUTH"] = "true"
os.environ["SUPABASE_URL"] = ""


@pytest.fixture(scope="session")
def client():
    db_file = ROOT / "tests" / ".test.db"
    db_file.unlink(missing_ok=True)
    from fastapi.testclient import TestClient

    from app.main import app
    from etl import load_sample

    load_sample.main()
    with TestClient(app) as c:
        yield c
    from app.db import engine

    engine.dispose()  # pooled connections keep the file locked on Windows
    db_file.unlink(missing_ok=True)


AUTH = {"Authorization": "Bearer dev:tester@example.com"}
