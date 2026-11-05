"""The route contracts (D40, D45): every write tagged ``sign-off`` declares the gate
dependency, every write tagged ``partner-only`` declares the partner dependency, every
write tagged ``material-conclusion`` declares the readiness dependency, and any route whose
path says it signs off, concludes or acknowledges carries the right tags. A route that
forgets one fails here before it ships."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from oak_misstatements.api.deps import PartnerDep
from oak_misstatements.api.evaluation import (
    MATERIAL_CONCLUSION,
    PARTNER_ONLY,
    SIGN_OFF,
    SignOffDep,
    conclusion_ready,
    sign_off_open,
)
from oak_misstatements.identity import current_partner
from oak_misstatements.main import create_app
from tests.conftest import APP_URL, IsolatedSettings, use_spine
from tests.test_api_evaluation import linked, raise_item, thresholds

SIGN_OFF_WORDS = ("sign-off", "signoff", "opinion")
PARTNER_WORDS = ("acknowledg", "conclusion")
READS = {"GET", "HEAD", "OPTIONS"}
ACKNOWLEDGE = "/api/engagements/{engagement_id}/evaluation/soft-gate-acknowledgements"
NOT_MATERIAL = "/api/engagements/{engagement_id}/evaluation/conclusions/not-material"
MATERIAL = "/api/engagements/{engagement_id}/evaluation/conclusions/material"


@dataclass(frozen=True)
class Write:
    path: str
    methods: frozenset[str]
    tags: tuple[str, ...]
    dependencies: frozenset[Callable[..., Any]]


def calls(dependant: Dependant) -> set[Callable[..., Any]]:
    found: set[Callable[..., Any]] = set()
    for sub in dependant.dependencies:
        if sub.call is not None:
            found.add(sub.call)
        found |= calls(sub)
    return found


def writes(app: FastAPI) -> list[Write]:
    """Every write route, whether mounted directly or through an included router (this
    FastAPI version keeps included routers nested and exposes their effective routes)."""
    found: list[Write] = []
    for entry in app.routes:
        contexts: Any
        if isinstance(entry, APIRoute):
            contexts = [entry]
        elif hasattr(entry, "effective_route_contexts"):
            contexts = list(entry.effective_route_contexts())
        else:
            continue
        for context in contexts:
            methods = frozenset(context.methods or ())
            if not methods - READS:
                continue
            found.append(
                Write(
                    context.path,
                    methods,
                    tuple(context.tags or ()),
                    frozenset(calls(context.dependant)),
                )
            )
    return found


def fresh_app() -> FastAPI:
    return create_app(IsolatedSettings(env="test", database_url=APP_URL, dev_user="t@firm"))


def test_every_tagged_write_declares_the_dependency_its_tag_promises() -> None:
    found = writes(fresh_app())
    assert found, "no write routes found: the walker no longer sees the API"
    for route in found:
        if SIGN_OFF in route.tags:
            assert sign_off_open in route.dependencies, route.path
        if PARTNER_ONLY in route.tags:
            assert current_partner in route.dependencies, route.path
        if MATERIAL_CONCLUSION in route.tags:
            assert conclusion_ready in route.dependencies, route.path
        lowered = route.path.lower()
        if any(word in lowered for word in SIGN_OFF_WORDS):
            assert SIGN_OFF in route.tags, f"{route.path} signs off and is not tagged"
        if any(word in lowered for word in PARTNER_WORDS):
            assert PARTNER_ONLY in route.tags, f"{route.path} is a partner action, not tagged"
        if "conclusion" in lowered:
            # D45: a conclusion is gated one way or the other, never ungated. Only the
            # conclusion that the misstatements are material may take the lighter gate.
            assert (SIGN_OFF in route.tags) != (MATERIAL_CONCLUSION in route.tags), route.path
            if MATERIAL_CONCLUSION in route.tags:
                assert lowered.endswith("/conclusions/material"), route.path


def test_the_partner_and_sign_off_writes_are_exactly_these() -> None:
    found = writes(fresh_app())
    assert sorted(route.path for route in found if PARTNER_ONLY in route.tags) == sorted(
        [ACKNOWLEDGE, NOT_MATERIAL, MATERIAL]
    )
    assert [route.path for route in found if SIGN_OFF in route.tags] == [NOT_MATERIAL]
    assert [route.path for route in found if MATERIAL_CONCLUSION in route.tags] == [MATERIAL]
    # Every other write is open to any authenticated identity, as the spec leaves it.
    for route in found:
        if PARTNER_ONLY not in route.tags:
            assert current_partner not in route.dependencies, route.path
    # The conclusion that the misstatements are not material takes the whole gate.
    not_material = next(route for route in found if route.path == NOT_MATERIAL)
    assert sign_off_open in not_material.dependencies
    assert conclusion_ready not in not_material.dependencies
    material = next(route for route in found if route.path == MATERIAL)
    assert conclusion_ready in material.dependencies
    assert sign_off_open not in material.dependencies


def test_another_sign_off_write_is_blocked_or_let_through_by_the_dependency(
    api: TestClient,
) -> None:
    """What any further sign-off route (an Opinion hand-off) will look like, mounted on the
    running test app: the dependency refuses with every reason while the gate blocks, and
    the partner check fails closed after it."""
    extra = APIRouter(prefix="/api", tags=[SIGN_OFF, PARTNER_ONLY])

    @extra.post("/engagements/{engagement_id}/opinion-probe")
    def hand_off(
        engagement_id: uuid.UUID, evaluation: SignOffDep, _partner: PartnerDep
    ) -> dict[str, Any]:
        return {"engagement_id": str(evaluation.engagement.id), "blocked": False}

    app = cast(FastAPI, api.app)
    app.include_router(extra)
    use_spine(api)
    engagement_id = linked(api)
    assert api.post(f"/api/engagements/{engagement_id}/opinion-probe").status_code == 409
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "400000.00")
    blocked = api.post(f"/api/engagements/{engagement_id}/opinion-probe")
    assert blocked.status_code == 409
    assert "hard gate" in blocked.json()["detail"]
    assert "M-1 is individually significant" in blocked.json()["detail"]
    clear = linked(api)
    thresholds(api, clear)
    raise_item(api, clear, "1000.00")
    assert api.post(f"/api/engagements/{clear}/opinion-probe").status_code == 403
    # The probe satisfies the contract exactly as a real route must.
    probe = next(route for route in writes(app) if route.path.endswith("opinion-probe"))
    assert sign_off_open in probe.dependencies and current_partner in probe.dependencies
    assert SIGN_OFF in probe.tags and PARTNER_ONLY in probe.tags
