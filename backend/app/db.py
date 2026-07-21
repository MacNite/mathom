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
    settings.source_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        # Background worker threads and request threads both write; without a
        # busy timeout concurrent writers fail immediately with "database is
        # locked". Wait up to 5s for the lock instead.
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def _column_names(conn: object, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).all()  # type: ignore[attr-defined]
    return {row[1] for row in rows}


def _add_user_id_column(conn: object, table: str) -> None:
    """Add the nullable ownership column to a legacy table (additive)."""
    if "user_id" not in _column_names(conn, table):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"))  # type: ignore[attr-defined]
        conn.execute(  # type: ignore[attr-defined]
            text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table}(user_id)")
        )


def _migrate_user_ownership(conn: object) -> None:
    """Bring pre-auth databases up to the user-management schema. Additive."""
    for table in ("mathoms", "tags", "collections"):
        _add_user_id_column(conn, table)

    # The legacy tags schema had a UNIQUE index on name; per-user tags need it
    # scoped to (user_id, name) instead. Replace it if the old one is present.
    index_rows = conn.execute(text("PRAGMA index_list(tags)")).all()  # type: ignore[attr-defined]
    for _seq, name, unique, *_ in index_rows:
        if name == "ix_tags_name" and unique:
            conn.execute(text("DROP INDEX ix_tags_name"))  # type: ignore[attr-defined]
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tags_name ON tags(name)"))  # type: ignore[attr-defined]
    conn.execute(  # type: ignore[attr-defined]
        text("CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_user_name ON tags(user_id, name)")
    )
    conn.execute(  # type: ignore[attr-defined]
        text("CREATE INDEX IF NOT EXISTS ix_collections_name ON collections(name)")
    )


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
        _migrate_user_ownership(conn)
        _migrate_segments(conn)
        _migrate_template_language(conn)
        _migrate_source_fields(conn)
        _migrate_vision_fields(conn)
        _migrate_local_auth(conn)


def refresh_fts(session: Session, mathom_id: int) -> None:
    """Rebuild the FTS row for one Mathom (rowid mirrors mathoms.id)."""
    row = session.execute(
        text(
            "SELECT m.title, COALESCE(m.transcript, '') || ' ' || "
            "COALESCE(m.visual_summary, '') || ' ' || COALESCE(m.visual_observations, ''), "
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


def _migrate_source_fields(conn: object) -> None:
    """Add source classification without disturbing existing recording rows."""
    for name, definition in (
        ("source_type", "VARCHAR(30) NOT NULL DEFAULT 'audio'"),
        ("source_path", "VARCHAR(1000) NOT NULL DEFAULT ''"),
    ):
        if name not in _column_names(conn, "mathoms"):
            conn.execute(text(f"ALTER TABLE mathoms ADD COLUMN {name} {definition}"))  # type: ignore[attr-defined]
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mathoms_source_type ON mathoms(source_type)"))  # type: ignore[attr-defined]


def _migrate_vision_fields(conn: object) -> None:
    """Add optional media/vision metadata without rewriting existing archives."""
    fields = (
        ("has_audio_stream", "BOOLEAN NOT NULL DEFAULT 1"),
        ("has_video_stream", "BOOLEAN NOT NULL DEFAULT 0"),
        ("vision_requested", "BOOLEAN NOT NULL DEFAULT 0"),
        ("vision_status", "VARCHAR(30) NOT NULL DEFAULT 'not_requested'"),
        ("vision_model", "VARCHAR(200)"),
        ("visual_summary", "TEXT"),
        ("visual_observations", "JSON"),
        ("vision_error_message", "TEXT"),
        ("vision_processed_at", "DATETIME"),
    )
    for name, definition in fields:
        if name not in _column_names(conn, "mathoms"):
            conn.execute(text(f"ALTER TABLE mathoms ADD COLUMN {name} {definition}"))  # type: ignore[attr-defined]
    conn.execute(  # type: ignore[attr-defined]
        text("CREATE INDEX IF NOT EXISTS ix_mathoms_vision_status ON mathoms(vision_status)")
    )


def _migrate_local_auth(conn: object) -> None:
    """Add local-auth fields without rebuilding SQLite tables; retain legacy subject."""
    if "users" not in [
        r[0]
        for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))  # type: ignore[attr-defined]
    ]:
        return
    for name, definition in (
        ("password_hash", "VARCHAR(500)"),
        ("must_change_password", "BOOLEAN NOT NULL DEFAULT 0"),
        ("updated_at", "DATETIME"),
    ):
        if name not in _column_names(conn, "users"):
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))  # type: ignore[attr-defined]
    # Legacy installations defined subject as NOT NULL because every account
    # originally came from Authentik. SQLite cannot relax NOT NULL in place, so
    # rebuild just this table while preserving ids referenced by archive rows
    # and sessions. This lets an existing auth-disabled installation create its
    # first local account with no OIDC subject.
    subject_info = next(
        (row for row in conn.execute(text("PRAGMA table_info(users)")) if row[1] == "subject"),  # type: ignore[attr-defined]
        None,
    )
    if subject_info is not None and subject_info[3]:
        conn.execute(  # type: ignore[attr-defined]
            text(
                "CREATE TABLE users_local_auth_new ("
                "id INTEGER NOT NULL PRIMARY KEY, "
                "subject VARCHAR(255), "
                "email VARCHAR(320) NOT NULL, "
                "name VARCHAR(200) NOT NULL, "
                "role VARCHAR(20) NOT NULL, "
                "is_active BOOLEAN NOT NULL, "
                "created_at DATETIME NOT NULL, "
                "password_hash VARCHAR(500), "
                "must_change_password BOOLEAN NOT NULL DEFAULT 0, "
                "updated_at DATETIME, "
                "last_login_at DATETIME, "
                "UNIQUE(subject), UNIQUE(email))"
            )
        )
        conn.execute(  # type: ignore[attr-defined]
            text(
                "INSERT INTO users_local_auth_new "
                "(id, subject, email, name, role, is_active, created_at, password_hash, "
                "must_change_password, updated_at, last_login_at) "
                "SELECT id, subject, email, name, role, is_active, created_at, password_hash, "
                "COALESCE(must_change_password, 0), COALESCE(updated_at, created_at), "
                "last_login_at FROM users"
            )
        )
        conn.execute(text("DROP TABLE users"))  # type: ignore[attr-defined]
        conn.execute(text("ALTER TABLE users_local_auth_new RENAME TO users"))  # type: ignore[attr-defined]
        conn.execute(text("CREATE INDEX ix_users_subject ON users(subject)"))  # type: ignore[attr-defined]
        conn.execute(text("CREATE INDEX ix_users_email ON users(email)"))  # type: ignore[attr-defined]
        conn.execute(text("CREATE INDEX ix_users_role ON users(role)"))  # type: ignore[attr-defined]
    # owner was a legacy role; SQLite has no enum constraint, so this is safe and idempotent.
    conn.execute(text("UPDATE users SET role = 'admin' WHERE role = 'owner'"))  # type: ignore[attr-defined]


def _migrate_template_language(conn: object) -> None:
    """Store the UI language selected when a recording is submitted."""
    if "template_language" not in _column_names(conn, "mathoms"):
        conn.execute(  # type: ignore[attr-defined]
            text(
                "ALTER TABLE mathoms ADD COLUMN template_language VARCHAR(10) NOT NULL DEFAULT 'en'"
            )
        )


def _migrate_segments(conn: object) -> None:
    """Add JSON timestamp segments for installations created before this feature."""
    if "segments" not in _column_names(conn, "mathoms"):
        conn.execute(text("ALTER TABLE mathoms ADD COLUMN segments JSON"))  # type: ignore[attr-defined]
