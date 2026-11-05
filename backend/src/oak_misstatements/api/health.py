"""The health check: the API is up. It touches no database."""

from __future__ import annotations

from fastapi import APIRouter

from oak_misstatements import __version__
from oak_misstatements.config import MODULE

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "module": MODULE, "version": __version__}
