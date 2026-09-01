from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.api import router
from app.db import Database

from app import models as models  # noqa: F401


DEFAULT_DATABASE_URL = (
    "sqlite:///./data/social_studio.db"
)


def create_app(
    database_url: str | None = None,
) -> FastAPI:
    db_url = (
        database_url
        or os.getenv(
            "DATABASE_URL",
            DEFAULT_DATABASE_URL,
        )
    )

    database = Database(
        db_url
    )

    @asynccontextmanager
    async def lifespan(
        application: FastAPI,
    ):
        database.create_all()

        yield

        database.dispose()

    application = FastAPI(
        title="Social Media Studio",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.state.db = database

    application.include_router(
        router
    )

    return application


app = create_app()
