"""API entry point."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from baraza import __version__
from baraza.api import auth, captures, health, meetings, minutes, segments, vexa_capture
from baraza.api.auth import require_user
from baraza.api.dependencies import close_capture_adapter
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
            await close_capture_adapter()

    app = FastAPI(title="Baraza", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def reject_foreign_origin(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """A browser always names its origin on a write. Refuse writes from pages we do not know.

        The session cookie is SameSite=Lax, which does not stop another page on the same site
        (another port or subdomain). Requests without an Origin (curl, scripts) pass: they have
        no ambient cookie to abuse.
        """
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin is not None and origin not in get_settings().cors_origins:
                return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        # If-Match carries the minutes version a person is editing (optimistic locking).
        allow_headers=["Content-Type", "If-Match"],
        expose_headers=["ETag", "X-Minutes-Status", "Retry-After"],
    )
    # Everything except the health check and sign in needs a signed in person.
    signed_in = [Depends(require_user)]
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(segments.router, dependencies=signed_in)
    app.include_router(captures.router, dependencies=signed_in)
    app.include_router(meetings.router, dependencies=signed_in)
    app.include_router(vexa_capture.router, dependencies=signed_in)
    app.include_router(minutes.router, dependencies=signed_in)

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
