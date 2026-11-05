"""FastAPI application factory.

Run with ``uvicorn oak_misstatements.main:create_app --factory --port 8003``. Creating the
app builds the engine but opens no connection; the first request that needs the database
does.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from oak_misstatements import __version__
from oak_misstatements.api import router
from oak_misstatements.config import Settings, get_settings
from oak_misstatements.db import make_engine, make_session_factory
from oak_misstatements.errors import install_error_handlers
from oak_misstatements.services.spine_client import build_spine_client


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    app = FastAPI(title="OAK Audit - Misstatements Rollup", version=__version__)
    app.state.settings = resolved
    app.state.engine = make_engine(resolved.database_url)
    app.state.session_factory = make_session_factory(app.state.engine)
    # The Financial Spine when OAK_SPINE_URL names one (D11); None means not configured.
    app.state.spine_client = build_spine_client(resolved)
    install_error_handlers(app)
    app.include_router(router)

    @app.middleware("http")
    async def _security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Audit-file content is never to be cached by an intermediary or guessed at by a
        # browser; every response says so.
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app
