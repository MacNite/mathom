"""Database engine, session dependency, and lightweight migrations (FTS5)."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _make_engine() -> Engine:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def init_db(engine: Engine | None = None) -> None:
    """Create tables and the FTS5 search index. Additive and idempotent."""
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS mathom_fts USING fts5("
                "title, transcript, summaries)"
            )
        )


def refresh_fts(session: Session, mathom_id: int) -> None:
    """Rebuild the FTS row for one Mathom (rowid mirrors mathoms.id)."""
    row = session.execute(
        text(
            "SELECT m.title, COALESCE(m.transcript, ''), "
            "COALESCE((SELECT group_concat(s.content, ' ') FROM summaries s "
            "WHERE s.mathom_id = m.id), '') "
            "FROM mathoms m WHERE m.id = :id"
        ),
        {"id": mathom_id},
    ).first()
    session.execute(text("DELETE FROM mathom_fts WHERE rowid = :id"), {"id": mathom_id})
    if row is not None:
        session.execute(
            text(
                "INSERT INTO mathom_fts(rowid, title, transcript, summaries) "
                "VALUES (:id, :title, :transcript, :summaries)"
            ),
            {"id": mathom_id, "title": row[0], "transcript": row[1], "summaries": row[2]},
        )


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
