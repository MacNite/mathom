"""Mathom backend application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import get_session_factory, init_db
from app.routers import chat, collections, health, mathoms, search, templates
from app.seed import seed_templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    with get_session_factory()() as session:
        seed_templates(session)
    yield


app = FastAPI(
    title="Mathom",
    summary="Your Local AI Memory House",
    version=health.VERSION,
    lifespan=lifespan,
)

API_PREFIX = "/api"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(mathoms.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)
app.include_router(collections.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
