"""SQLAlchemy models for the mathom."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# The only supported roles. Legacy owner values are migrated to admin.
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_USER)


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_aware(value: datetime) -> datetime:
    """Coerce a possibly-naive stored datetime to aware UTC.

    SQLite does not preserve tzinfo, so datetimes read back from the database
    come back naive; comparing them against the aware ``utcnow()`` raises a
    ``TypeError``. We always store UTC, so treat any naive value as UTC.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


mathom_tags = Table(
    "mathom_tags",
    Base.metadata,
    Column("mathom_id", ForeignKey("mathoms.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

collection_mathoms = Table(
    "collection_mathoms",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("mathom_id", ForeignKey("mathoms.id", ondelete="CASCADE"), primary_key=True),
)


class Mathom(Base):
    """One uploaded recording and everything gathered around it."""

    __tablename__ = "mathoms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Owning user. NULL means "unowned" — the single-user / auth-disabled case,
    # and rows that predate user management (claimed by the Owner on first login).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), default="Untitled Mathom")
    original_filename: Mapped[str] = mapped_column(String(500), default="")
    audio_path: Mapped[str] = mapped_column(String(1000), default="")
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    template_language: Mapped[str] = mapped_column(String(10), default="en")
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    summaries: Mapped[list[Summary]] = relationship(
        back_populates="mathom", cascade="all, delete-orphan", order_by="Summary.created_at"
    )
    chat_messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="mathom", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )
    tags: Mapped[list[Tag]] = relationship(secondary=mathom_tags, back_populates="mathoms")
    collections: Mapped[list[Collection]] = relationship(
        secondary=collection_mathoms, back_populates="mathoms"
    )


class Job(Base):
    """A durable unit of background work for a Mathom.

    Persisting the intent to process (instead of relying on in-process
    ``BackgroundTasks``) means work survives a restart: a single worker thread
    claims queued jobs, and anything left ``running`` by a crash is requeued.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mathom_id: Mapped[int] = mapped_column(ForeignKey("mathoms.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="process")
    template_slug: Mapped[str] = mapped_column(String(100), default="general-summary")
    # queued → running → done | error
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Earliest time this job may be claimed (used for retry backoff).
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Summary(Base):
    """An AI output produced for a Mathom with a given prompt template."""

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mathom_id: Mapped[int] = mapped_column(ForeignKey("mathoms.id", ondelete="CASCADE"), index=True)
    template_slug: Mapped[str] = mapped_column(String(100), default="general-summary")
    template_name: Mapped[str] = mapped_column(String(200), default="General Summary")
    content: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    mathom: Mapped[Mathom] = relationship(back_populates="summaries")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mathom_id: Mapped[int] = mapped_column(ForeignKey("mathoms.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    mathom: Mapped[Mathom] = relationship(back_populates="chat_messages")


class Tag(Base):
    __tablename__ = "tags"
    # Tag vocabulary is per-user: the same name may exist once per owner.
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tags_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), index=True)

    mathoms: Mapped[list[Mathom]] = relationship(secondary=mathom_tags, back_populates="tags")


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_collections_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    mathoms: Mapped[list[Mathom]] = relationship(
        secondary=collection_mathoms, back_populates="collections"
    )


class PromptTemplate(Base):
    """Editable prompt template; seed copies come from prompt-templates/."""

    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text)  # must contain {transcript}
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    """A person who signs in through Authentik. Only used when auth is enabled."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Legacy Authentik subject; retained so existing installations can sign in.
    subject: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default=ROLE_USER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    password_hash: Mapped[str | None] = mapped_column(String(500), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def has_local_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def has_authentik_identity(self) -> bool:
        return bool(self.subject)


class Invitation(Base):
    """A single-use, revocable local-account registration invitation."""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    """Server-side session; the opaque token lives in an HttpOnly cookie."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class OAuthState(Base):
    """Short-lived CSRF/nonce state for an in-flight OAuth login."""

    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    nonce: Mapped[str] = mapped_column(String(128), default="")
    redirect_to: Mapped[str] = mapped_column(String(500), default="/")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    """Owner-editable key/value settings (e.g. Authentik connection details)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
