"""Mathom backend application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import get_session_factory, init_db
from app.ratelimit import RateLimitMiddleware
from app.routers import (
    auth,
    chat,
    collections,
    health,
    mathoms,
    search,
    settings,
    templates,
    users,
)
from app.seed import seed_templates
from app.services import jobs, pipeline
from app.services.worker import worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    with get_session_factory()() as session:
        seed_templates(session)
    # Resume work interrupted by a previous restart: requeue jobs left running,
    # then flip any Mathom no live job still owns to a retryable error.
    jobs.recover_stuck()
    pipeline.recover_interrupted_jobs()
    worker.start()
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(
    title="Mathom",
    summary="mathom",
    version=health.VERSION,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)

API_PREFIX = "/api"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(settings.router, prefix=API_PREFIX)
app.include_router(mathoms.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)
app.include_router(collections.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
