"""The API routers: the health check, engagements, misstatements (Stage 1), thresholds
(Stage 2) and the evaluation with its gates (D38). The state machine arrives with Stage 3."""

from __future__ import annotations

from fastapi import APIRouter

from oak_misstatements.api.engagements import router as engagements_router
from oak_misstatements.api.evaluation import router as evaluation_router
from oak_misstatements.api.health import router as health_router
from oak_misstatements.api.misstatements import router as misstatements_router
from oak_misstatements.api.thresholds import router as thresholds_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(engagements_router)
router.include_router(misstatements_router)
router.include_router(thresholds_router)
router.include_router(evaluation_router)

__all__ = ["router"]
