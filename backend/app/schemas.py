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


# --- Auth / users / settings ------------------------------------------------


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    has_local_password: bool = False
    has_authentik_identity: bool = False


class AuthStatus(BaseModel):
    """Everything the frontend needs to render the login state."""

    auth_enabled: bool
    configured: bool
    authenticated: bool
    onboarding_required: bool = False
    local_login_available: bool = True
    authentik_configured: bool = False
    login_url: str
    user: UserOut | None = None


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|user)$")
    is_active: bool | None = None
    email: str | None = Field(default=None, max_length=320)
    name: str | None = Field(default=None, max_length=200)


class LocalLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class OnboardingCreate(BaseModel):
    name: str = Field(default="", max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    password_confirmation: str = Field(min_length=12, max_length=256)


class UserCreate(BaseModel):
    name: str = Field(default="", max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    must_change_password: bool = True


class PasswordChange(BaseModel):
    current_password: str | None = Field(default=None, max_length=256)
    password: str = Field(min_length=12, max_length=256)


class AuthentikSettingsOut(BaseModel):
    issuer: str
    client_id: str
    scopes: str
    public_base_url: str
    auto_create_users: bool
    verify_ssl: bool
    configured: bool
    # The secret itself is never returned; the UI only learns whether one is set.
    client_secret_set: bool


class AuthentikSettingsUpdate(BaseModel):
    issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str | None = None
    public_base_url: str | None = None
    auto_create_users: bool | None = None
    verify_ssl: bool | None = None
