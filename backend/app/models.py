"""SQLAlchemy models for the Mathom-house."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


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
    title: Mapped[str] = mapped_column(String(300), default="Untitled Mathom")
    original_filename: Mapped[str] = mapped_column(String(500), default="")
    audio_path: Mapped[str] = mapped_column(String(1000), default="")
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    mathoms: Mapped[list[Mathom]] = relationship(secondary=mathom_tags, back_populates="tags")


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
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
