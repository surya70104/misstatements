"""The Financial Spine double served over HTTP for browser checks (architecture D11), on
port 8013 by default. It wraps the same ``FakeSpine`` the test suite uses: every answer is the
fixture's, nothing is live, and the server holds no state beyond the process.

    .venv\\Scripts\\python.exe -m tests.local_stubs --spine-port 8013

Point a development backend at it with OAK_SPINE_URL=http://127.0.0.1:8013. This module is
development tooling only and is never imported by the application.
"""

from __future__ import annotations

import argparse

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from tests.fake_spine import FakeSpine


def wrap(spine: FakeSpine) -> Starlette:
    """A Starlette app that forwards every request to the double's handler."""

    async def relay(request: Request) -> Response:
        body = await request.body()
        forwarded = httpx.Request(
            request.method, str(request.url), headers=dict(request.headers), content=body
        )
        answer = spine.handle(forwarded)
        return Response(
            answer.content,
            status_code=answer.status_code,
            headers={"content-type": answer.headers.get("content-type", "application/json")},
        )

    return Starlette(routes=[Route("/{path:path}", relay, methods=["GET", "POST"])])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spine-port", type=int, default=8013)
    args = parser.parse_args()
    print(f"Financial Spine double on http://127.0.0.1:{args.spine_port} (nothing is live)")
    uvicorn.run(wrap(FakeSpine()), host="127.0.0.1", port=args.spine_port, log_level="warning")


if __name__ == "__main__":
    main()
