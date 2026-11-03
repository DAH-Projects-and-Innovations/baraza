"""API entry point."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from baraza import __version__
from baraza.api import captures, health, meetings, segments
from baraza.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Baraza", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(segments.router)
    app.include_router(captures.router)
    app.include_router(meetings.router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: object, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ]
            },
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("baraza.main:app", host="0.0.0.0", port=8000)
