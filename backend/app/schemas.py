"""Pydantic schemas for the API surface."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TagOut(ORMModel):
    id: int
    name: str


class SummaryOut(ORMModel):
    id: int
    template_slug: str
    template_name: str
    content: str
    model: str
    created_at: datetime


class ChatMessageOut(ORMModel):
    id: int
    role: str
    content: str
    created_at: datetime


class CollectionBrief(ORMModel):
    id: int
    name: str


class MathomListItem(ORMModel):
    id: int
    title: str
    status: str
    duration_seconds: float | None
    language: str | None
    favorite: bool
    archived: bool
    created_at: datetime
    tags: list[TagOut] = []


class MathomOut(MathomListItem):
    original_filename: str
    error_message: str | None
    transcript: str | None
    summaries: list[SummaryOut] = []
    chat_messages: list[ChatMessageOut] = []
    collections: list[CollectionBrief] = []


class MathomUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    favorite: bool | None = None
    archived: bool | None = None
    transcript: str | None = None


class SummaryCreate(BaseModel):
    template_slug: str = "general-summary"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class CollectionOut(ORMModel):
    id: int
    name: str
    description: str
    created_at: datetime
    mathoms: list[MathomListItem] = []


class TemplateCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    prompt: str = Field(min_length=1)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    prompt: str | None = Field(default=None, min_length=1)


class TemplateOut(ORMModel):
    id: int
    slug: str
    name: str
    description: str
    prompt: str
    is_builtin: bool
    updated_at: datetime


class SearchHit(BaseModel):
    mathom: MathomListItem
    snippet: str


class TimelineBucket(BaseModel):
    month: str  # "YYYY-MM"
    count: int


class HealthOut(BaseModel):
    status: str
    version: str
    ollama_reachable: bool
