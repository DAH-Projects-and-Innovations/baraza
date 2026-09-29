"""API entry point."""

from fastapi import FastAPI

from baraza import __version__
from baraza.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="Baraza", version=__version__)
    app.include_router(health.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("baraza.main:app", host="0.0.0.0", port=8000)
