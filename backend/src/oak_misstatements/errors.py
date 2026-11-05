"""Domain errors raised by services and turned into HTTP responses by the app."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ModuleError(Exception):
    status_code = 400


class NotFound(ModuleError):
    status_code = 404


class Conflict(ModuleError):
    """The action does not fit the current state (wrong state, locked version, reused
    reference)."""

    status_code = 409


class PendingDecision(Conflict):
    """The action depends on an accounting or business decision nobody has taken yet
    (``docs/DECISIONS_PENDING.md``; architecture D20, D23). Nothing was written."""

    def __init__(self, decision: str, message: str) -> None:
        super().__init__(f"{message} (pending decision {decision}; docs/DECISIONS_PENDING.md)")
        self.decision = decision


class Invalid(ModuleError):
    """The content does not satisfy a rule of the specification."""

    status_code = 422


class Forbidden(ModuleError):
    status_code = 403


class ServiceUnavailable(ModuleError):
    """Another module (the Spine, the Binder, WorkMind) cannot be reached or refused the
    call; nothing was half-done."""

    status_code = 503


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ModuleError)
    async def _module_error(_request: Request, error: ModuleError) -> JSONResponse:
        content: dict[str, str] = {"detail": str(error)}
        if isinstance(error, PendingDecision):
            content["pending_decision"] = error.decision
        return JSONResponse(status_code=error.status_code, content=content)
