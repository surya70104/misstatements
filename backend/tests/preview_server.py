"""An isolated preview of the whole module, for looking at the screens on live data
(register V9 and V10; architecture D52). Development tooling only: nothing in the
application imports it, and it changes nothing permanently.

    .venv\\Scripts\\python.exe -m tests.preview_server --port 8014

What it is, exactly:

- **The real application.** ``create_app`` with its real routes, services, guards and error
  handling, served by uvicorn over real HTTP.
- **A real PostgreSQL database, and nothing kept.** Every request's session is bound to one
  connection to ``oak_misstatements_test``, as the application role, inside ONE transaction
  that is never committed. A request's commit releases a savepoint, exactly as in the test
  suite's ``api`` fixture. When the process ends the transaction is rolled back, or dropped
  by PostgreSQL if the process is killed, and the database is as it was: no row remains.
  ``oak_misstatements`` is never connected to: the settings carry a placeholder for it and
  the engine built from it is disposed before any request is served.
- **The Financial Spine double**, the same ``FakeSpine`` the test suite uses. Nothing here
  reaches a live Spine; that is V5 and V6, and it is not claimed.
- **Development identity.** Writes are recorded as the development user. No partner is
  named and none can be: the partner-only actions are refused, as they are for anyone
  until the firm wires its identity provider (B9a, O1).
- **The built frontend** from ``frontend/dist``, served from the same port, so a browser
  talks to this preview and to nothing else.

Why not a separate preview database: no role this project has may create a database, and
the settings refuse any database but ``oak_misstatements`` and ``oak_misstatements_test``
by design (``check_database_url``). A third database would need a superuser and a change to
that guard, which are a person's to decide.

Requests are served one at a time, because they share one connection.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, MutableMapping
from decimal import Decimal
from typing import Any

import uvicorn
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from starlette.staticfiles import StaticFiles

from oak_misstatements.db import make_engine
from oak_misstatements.main import create_app
from tests.conftest import APP_URL, BACKEND_DIR, IsolatedSettings, test_url
from tests.fake_spine import FakeSpine

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
App = Callable[[Scope, Receive, Send], Awaitable[None]]

DIST = BACKEND_DIR.parent / "frontend" / "dist"
PREVIEW_USER = "preview@localhost"


class OneAtATime:
    """Serve one request at a time: every session shares one connection."""

    def __init__(self, app: App) -> None:
        self.app = app
        self.lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        async with self.lock:
            await self.app(scope, receive, send)


def main() -> None:
    parser = argparse.ArgumentParser(description="An isolated, rolled-back preview")
    parser.add_argument("--port", type=int, default=8014)
    parser.add_argument(
        "--strategy-fraction",
        type=Decimal,
        default=None,
        help="A TEST value for OAK_STRATEGY_TRIGGER_FRACTION, so the strategy prompt can be "
        "looked at. What the firm's value should be is pending decision B5; this sets none.",
    )
    args = parser.parse_args()

    url = test_url("OAK_TEST_APP_DATABASE_URL")
    if not url:
        raise SystemExit(
            "OAK_TEST_APP_DATABASE_URL is not set: the preview needs the test database"
        )

    settings = IsolatedSettings(
        env="test",
        database_url=APP_URL,
        dev_user=PREVIEW_USER,
        strategy_trigger_fraction=args.strategy_fraction,
    )
    app = create_app(settings)
    app.state.engine.dispose()  # the placeholder for the main database is never used

    engine = make_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        database = connection.execute(text("select current_database()")).scalar_one()
        if database != "oak_misstatements_test":
            transaction.rollback()
            raise SystemExit(f"refusing to preview on {database!r}")
        app.state.session_factory = sessionmaker(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        app.state.backing_store = "postgresql"
        app.state.spine_client = FakeSpine().client()
        if DIST.is_dir():
            app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
        print(
            f"Preview on http://127.0.0.1:{args.port} over {database}, in one transaction "
            "that is never committed. Financial Spine: the test double. Identity: "
            f"{PREVIEW_USER} (development mode; no partner can be named).",
            flush=True,
        )
        try:
            uvicorn.run(OneAtATime(app), host="127.0.0.1", port=args.port, log_level="warning")
        finally:
            transaction.rollback()
            print("Preview ended: the transaction was rolled back; nothing was kept.", flush=True)
    engine.dispose()


if __name__ == "__main__":
    main()
