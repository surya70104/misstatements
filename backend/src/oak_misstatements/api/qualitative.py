"""The qualitative checklist of a misstatement (spec section 5; acceptance 8; D59): read it,
record a factor with its reason, record it again with a new reason, or clear it. Every write
appends an entry; none changes or removes an earlier one. A misstatement with at least one
factor recorded is escalated, and is then listed individually and accumulated whatever its
size (see ``core/gates.py``)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from oak_misstatements.api.deps import SessionDep, SettingsDep, UserDep
from oak_misstatements.schemas.qualitative import QualitativeClearIn, QualitativeIn
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.qualitative import (
    checklist_json,
    clear_factor,
    read_checklist,
    record_factor,
)

router = APIRouter(tags=["qualitative"])


@router.get("/misstatements/{misstatement_id}/qualitative")
def read(misstatement_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
    """The checklist: each of the seven factors, whether it applies now and why, whether the
    misstatement is escalated, and every entry ever made."""
    misstatement, entries = read_checklist(session, misstatement_id)
    return {**checklist_json(misstatement, entries), "authorisation": authorisation_json(settings)}


@router.post("/misstatements/{misstatement_id}/qualitative", status_code=201)
def record(
    misstatement_id: uuid.UUID,
    body: QualitativeIn,
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Record a factor with its reason, which escalates the misstatement; or record a factor
    again with a new reason. Who may do so is the firm's to decide (register B9b): any
    authenticated identity, as for the module's other writes."""
    misstatement, entries = record_factor(
        session, misstatement_id, factor=body.factor, note=body.note, actor=user
    )
    return {**checklist_json(misstatement, entries), "authorisation": authorisation_json(settings)}


@router.post("/misstatements/{misstatement_id}/qualitative/{factor}/clear", status_code=201)
def clear(
    misstatement_id: uuid.UUID,
    factor: str,
    body: QualitativeClearIn,
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Clear a recorded factor, with the reason. The earlier entries stay. When no factor
    applies any more the misstatement is no longer escalated."""
    misstatement, entries = clear_factor(
        session, misstatement_id, factor=factor, note=body.note, actor=user
    )
    return {**checklist_json(misstatement, entries), "authorisation": authorisation_json(settings)}
