"""API entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from baraza import __version__
from baraza.api import captures, health, minutes, segments
from baraza.config import get_settings
from baraza.db.session import Database


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(get_settings().database_url)
        app.state.database = database
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(title="Baraza", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(segments.router)
    app.include_router(captures.router)
    app.include_router(captures.frontend_router)
    app.include_router(minutes.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("baraza.main:app", host="0.0.0.0", port=8000)
