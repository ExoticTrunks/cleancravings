from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def normalise_url(url: str) -> str:
    """Supabase's dashboard hands out postgresql://... URLs, which SQLAlchemy maps to psycopg2.
    We ship psycopg 3, so point those at it."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str | None = None):
    url = normalise_url(url or get_settings().database_url)
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        # SQLite ignores foreign keys unless asked
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind=None) -> None:
    from . import models  # noqa: F401  (registers tables)

    bind = bind or engine
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        with bind.begin() as conn:
            for stmt in rls_statements(bind.dialect):
                conn.execute(text(stmt))


def rls_statements(dialect) -> list[str]:
    """Supabase serves the public schema through its REST API to anyone holding the anon key.
    RLS with no policies gives those roles nothing, which keeps health profiles and visits private
    (NFR-7). Our backend connects as the tables' owner, and RLS doesn't apply to owners unless
    FORCEd, so the API and ETL are unaffected. Enabling it again is a no-op."""
    prep = dialect.identifier_preparer
    return [f"ALTER TABLE {prep.format_table(t)} ENABLE ROW LEVEL SECURITY" for t in Base.metadata.sorted_tables]
