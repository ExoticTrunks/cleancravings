"""init_db: RLS on every app table when running on Postgres (Supabase).

The last test only runs against a real Postgres:

    TEST_DATABASE_URL=postgresql://... pytest tests/test_db.py

It doesn't use the `client` fixture, so it never loads sample data into that database.
"""

import os

import pytest
from sqlalchemy import event, text
from sqlalchemy.dialects import postgresql

from app import models  # noqa: F401  (registers tables)
from app.db import Base, init_db, make_engine, normalise_url, rls_statements

PG_URL = os.environ.get("TEST_DATABASE_URL", "")
on_postgres = pytest.mark.skipif(not PG_URL.startswith(("postgres://", "postgresql")), reason="needs TEST_DATABASE_URL=postgresql://...")


def test_normalise_url_uses_psycopg3():
    assert normalise_url("postgresql://u:p@host:5432/postgres") == "postgresql+psycopg://u:p@host:5432/postgres"
    assert normalise_url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalise_url("postgresql+psycopg://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalise_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_rls_statement_for_every_table():
    stmts = rls_statements(postgresql.dialect())
    assert len(stmts) == len(Base.metadata.tables) > 0
    for t in Base.metadata.tables:
        assert f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY" in stmts
    assert "ALTER TABLE app_user ENABLE ROW LEVEL SECURITY" in stmts  # health profiles hang off this


def test_sqlite_gets_no_rls_statements():
    eng = make_engine("sqlite://")
    seen: list[str] = []
    event.listen(eng, "before_cursor_execute", lambda *a: seen.append(a[2]))
    init_db(eng)
    assert seen and not any("ROW LEVEL SECURITY" in s for s in seen)


@on_postgres
def test_postgres_tables_have_rls_enabled():
    eng = make_engine(PG_URL)
    try:
        init_db(eng)
        init_db(eng)  # running again (every app start and ETL run) must be harmless
        with eng.connect() as conn:
            rows = dict(
                conn.execute(
                    text("SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = current_schema() AND tablename = ANY(:names)"),
                    {"names": list(Base.metadata.tables)},
                ).all()
            )
            # The connecting role still reads its own tables: RLS isn't forced on owners
            conn.execute(text("SELECT count(*) FROM hawker_centre")).scalar_one()
    finally:
        eng.dispose()
    assert set(rows) == set(Base.metadata.tables), "every app table should exist"
    assert [t for t, on in rows.items() if not on] == []
