"""The misstatement record (spec sections 3, 4, 6.1, 8, 9): raise one, list an engagement's,
read one with its versions. Every amount in an answer comes from the Spine's lines at the
moment of the request; every effect is computed on the classification recorded when the
version was raised, with the Spine's current classification compared beside it (D32); every
band is computed on read against the engagement's current threshold version (D33)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.config import Settings
from oak_misstatements.core.banding import (
    CLASSIFICATION_ONLY_BASIS,
    NO_EFFECTS_BASIS,
    NO_THRESHOLDS_BASIS,
    UNRESOLVED_BASIS,
    band_item,
    range_crosses_pm,
)
from oak_misstatements.core.effects import Effects, Line
from oak_misstatements.core.states import expected_spine_status
from oak_misstatements.models import (
    Misstatement,
    MisstatementVersion,
    QualitativeFactor,
    Threshold,
)
from oak_misstatements.schemas import amount
from oak_misstatements.schemas.misstatements import MisstatementIn
from oak_misstatements.schemas.transitions import TransitionIn
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.misstatements import (
    Classification,
    SpineView,
    current_versions,
    get_misstatement,
    measure,
    raise_misstatement,
    spine_views,
)
from oak_misstatements.services.qualitative import (
    detail_json,
    entries_by_misstatement,
    summary_json,
)
from oak_misstatements.services.thresholds import current_threshold, lines_of
from oak_misstatements.services.transitions import SpineOutcome, transition

router = APIRouter(tags=["misstatements"])


def _time(value: dt.datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _optional_amount(value: Any) -> str | None:
    return None if value is None else amount(value)


def version_json(version: MisstatementVersion) -> dict[str, Any]:
    return {
        "version_no": version.version_no,
        "type": version.type,
        "description": version.description,
        "raised_by": version.raised_by,
        "raised_from": version.raised_from,
        "source_ref": version.source_ref,
        # Spec section 8 (D64): a run's id and citations, or a note's reference and link.
        "origin": version.origin,
        "state": version.state,
        "communicated_at": _time(version.communicated_at),
        "decided_at": _time(version.decided_at),
        "refusal_reason": version.refusal_reason,
        "withdrawal_reason": version.withdrawal_reason,
        "spine_adjustment_id": str(version.spine_adjustment_id),
        "spine_kind": version.spine_kind,
        "range_low": _optional_amount(version.range_low),
        "range_high": _optional_amount(version.range_high),
        "sample_ref": version.sample_ref,
        "projection_basis": version.projection_basis,
        "created_by": version.created_by,  # who made this version: who moved the state
        "created_at": _time(version.created_at),
    }


def line_json(line: Line) -> dict[str, Any]:
    return {
        "ledger_key": line.ledger_key,
        "ledger_name": line.ledger_name,
        "parent_chain": list(line.parent_chain),
        "head_id": line.head_id,
        "nature": line.nature,
        "section": line.section,
        "dr": amount(line.dr),
        "cr": amount(line.cr),
    }


def effects_json(effects: Effects, classification: Classification | None) -> dict[str, Any]:
    # Both effects are null together when any line cannot be classified or matched (D31,
    # D32): no partial total is ever shown and nothing is substituted with zero.
    return {
        "profit_before_tax": _optional_amount(effects.profit_before_tax),
        "profit_basis": effects.profit_basis,
        "profit_partial": effects.profit_partial,  # the earlier name for ``partial``
        "net_assets": _optional_amount(effects.net_assets),
        "net_assets_basis": effects.net_assets_basis,
        "partial": effects.partial,
        "unresolved": list(effects.unresolved),
        "captions": [
            {"head_id": caption.head_id, "nature": caption.nature, "signed": amount(caption.signed)}
            for caption in effects.captions
        ],
        "classification_only": effects.classification_only,
        # The classification the effects were computed on (D32): recorded when the version was
        # raised, never the Spine's current one.
        "spine_version_at_raise": (
            None
            if classification is None or classification.spine_version_at_raise is None
            else str(classification.spine_version_at_raise)
        ),
        "tree_version_at_raise": (
            None if classification is None else classification.tree_version_at_raise
        ),
    }


def classification_json(view: SpineView) -> dict[str, Any] | None:
    classification = view.classification
    if classification is None:
        return None
    return {
        "spine_version_at_raise": (
            None
            if classification.spine_version_at_raise is None
            else str(classification.spine_version_at_raise)
        ),
        "tree_version_at_raise": classification.tree_version_at_raise,
        "tree_version_now": classification.tree_version_now,
        "drift": [
            {
                "position": entry.position,
                "ledger_name": entry.ledger_name,
                "ledger_key": entry.ledger_key,
                "parent_chain": list(entry.parent_chain),
                "snapshot": {"head_id": entry.snapshot_head_id, "section": entry.snapshot_section},
                "live": {"head_id": entry.live_head_id, "section": entry.live_section},
            }
            for entry in classification.drift
        ],
        "unmatched": list(classification.unmatched),
        "effects_on_current_classification": (
            None
            if classification.effects_on_current is None
            else effects_json(classification.effects_on_current, None)
        ),
    }


def band_json(
    view: SpineView, current: MisstatementVersion, threshold: Threshold | None
) -> dict[str, Any]:
    """Spec section 4 (D33): both effects banded against the current threshold version, the
    item's band the higher of the two; null, with the reason, when nothing can be banded."""
    body: dict[str, Any] = {
        "band": None,
        "bands": None,
        "amounts": None,
        "threshold_id": None if threshold is None else str(threshold.id),
        "threshold_version_no": None if threshold is None else threshold.version_no,
        "basis": None,
        # Spec 3.2: a projected item is never treated as factual without saying so, and a
        # judgemental item carries its range beside the point estimate it is banded on.
        "projected": current.type == "projected",
        "range_crosses_pm": None,
        # D37: a classification-only item is trivial on amount and says so.
        "classification_only": view.effects is not None and view.effects.classification_only,
    }
    if threshold is None:
        body["basis"] = NO_THRESHOLDS_BASIS
        return body
    lines = lines_of(threshold)
    if current.type == "judgemental":
        body["range_crosses_pm"] = range_crosses_pm(current.range_low, current.range_high, lines)
    if view.effects is None:
        body["basis"] = NO_EFFECTS_BASIS
        return body
    result = band_item(
        view.effects,
        lines,
        threshold_id=threshold.id,
        threshold_version_no=threshold.version_no,
        range_low=current.range_low,
        range_high=current.range_high,
    )
    if result is None:
        body["basis"] = UNRESOLVED_BASIS.format(names=", ".join(view.effects.unresolved) or "none")
        return body
    body["band"] = result.band.value
    body["bands"] = {"profit": result.profit_band.value, "net_assets": result.net_assets_band.value}
    body["amounts"] = {
        "profit": amount(result.profit_amount),
        "net_assets": amount(result.net_assets_amount),
    }
    body["basis"] = CLASSIFICATION_ONLY_BASIS if body["classification_only"] else result.basis
    return body


def spine_json(view: SpineView) -> dict[str, Any]:
    adjustment = view.adjustment
    return {
        "status": view.state,
        "detail": view.detail,
        "adjustment_id": None if adjustment is None else str(adjustment.adjustment_id),
        "adjustment_status": None if adjustment is None else adjustment.status,
        "kind": None if adjustment is None else adjustment.kind,
        "finding_ref": None if adjustment is None else adjustment.finding_ref,
        "proposed_by": None if adjustment is None else adjustment.proposed_by,
        "proposed_at": None if adjustment is None else _time(adjustment.proposed_at),
        "decided_by": None if adjustment is None else adjustment.decided_by,
        "decided_at": None if adjustment is None else _time(adjustment.decided_at),
        "decision_note": None if adjustment is None else adjustment.decision_note,
        "measure": _optional_amount(measure(view)),
        "tree_version_now": view.tree_version_now,
        "lines": [line_json(line) for line in view.lines],
    }


def consistency_json(view: SpineView, current: MisstatementVersion) -> dict[str, Any]:
    """Whether the state here and the Spine's adjustment agree (D41). ``consistent`` is null
    when the Spine could not be read; a disagreement is reported, never repaired."""
    expected = expected_spine_status(current.state)
    actual = None if view.adjustment is None else view.adjustment.status
    consistent = None if actual is None else actual == expected
    detail = None
    if consistent is False:
        detail = (
            f"this misstatement is {current.state} here, which expects the Spine's "
            f"adjustment to be {expected}; the Spine holds it {actual}. A person must "
            "reconcile the two; nothing is changed automatically (architecture D41)"
        )
    return {
        "consistent": consistent,
        "state": current.state,
        "expected_adjustment_status": expected,
        "adjustment_status": actual,
        "detail": detail,
    }


def misstatement_json(
    misstatement: Misstatement,
    current: MisstatementVersion,
    view: SpineView,
    threshold: Threshold | None,
    settings: Settings,
    *,
    versions: list[MisstatementVersion] | None = None,
    entries: Sequence[QualitativeFactor] = (),
) -> dict[str, Any]:
    banding = band_json(view, current, threshold)
    body: dict[str, Any] = {
        "id": str(misstatement.id),
        "engagement_id": str(misstatement.engagement_id),
        "ref": misstatement.ref,
        "created_by": misstatement.created_by,
        "created_at": _time(misstatement.created_at),
        "current": version_json(current),
        "spine": spine_json(view),
        "state_consistency": consistency_json(view, current),
        "effects": (
            None if view.effects is None else effects_json(view.effects, view.classification)
        ),
        "classification": classification_json(view),
        # ``band`` and ``band_basis`` keep their Stage 2 names; ``banding`` carries the detail.
        "band": banding["band"],
        "band_basis": banding["basis"],
        "banding": banding,
        # Spec section 5: escalated while a qualitative factor is recorded (D59). One
        # misstatement read on its own carries the whole checklist and its history as well
        # (spec section 10.2); a row of the schedule carries the summary.
        "qualitative": summary_json(entries) if versions is None else detail_json(entries),
        "authorisation": authorisation_json(settings),
    }
    if versions is not None:
        body["versions"] = [version_json(version) for version in versions]
    return body


@router.post("/engagements/{engagement_id}/misstatements", status_code=201)
def create(
    engagement_id: uuid.UUID,
    body: MisstatementIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    engagement = get_engagement(session, engagement_id)
    misstatement, version, view = raise_misstatement(
        session, spine, engagement, body, raised_by=user
    )
    threshold = current_threshold(session, engagement)
    return misstatement_json(misstatement, version, view, threshold, settings, versions=[version])


@router.get("/engagements/{engagement_id}/misstatements")
def index(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> list[dict[str, Any]]:
    engagement = get_engagement(session, engagement_id)
    pairs = current_versions(session, engagement)
    views = spine_views(session, spine, engagement, [version for _misstatement, version in pairs])
    threshold = current_threshold(session, engagement)
    entries = entries_by_misstatement(session, [misstatement.id for misstatement, _v in pairs])
    return [
        misstatement_json(
            misstatement,
            version,
            views[version.id],
            threshold,
            settings,
            entries=entries[misstatement.id],
        )
        for misstatement, version in pairs
    ]


@router.get("/misstatements/{misstatement_id}")
def read(
    misstatement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    misstatement, versions = get_misstatement(session, misstatement_id)
    engagement = get_engagement(session, misstatement.engagement_id)
    current = versions[-1]
    views = spine_views(session, spine, engagement, [current])
    threshold = current_threshold(session, engagement)
    entries = entries_by_misstatement(session, [misstatement.id])[misstatement.id]
    return misstatement_json(
        misstatement,
        current,
        views[current.id],
        threshold,
        settings,
        versions=versions,
        entries=entries,
    )


def outcome_json(outcome: SpineOutcome) -> dict[str, Any]:
    return {
        "spine_decision": outcome.decision,
        "decided_now": outcome.decided_now,
        "note": outcome.note,
        "adjustment_status": None if outcome.adjustment is None else outcome.adjustment.status,
    }


@router.post("/misstatements/{misstatement_id}/transitions", status_code=201)
def move(
    misstatement_id: uuid.UUID,
    body: TransitionIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Move a misstatement along the state machine (spec section 3.3): communicate, then
    correct, refuse with a reason, or withdraw with a reason. A new append-only version each
    time; a correction is accepted in the Spine and posts; nothing else posts (D41)."""
    misstatement, versions, outcome = transition(session, spine, misstatement_id, body, actor=user)
    engagement = get_engagement(session, misstatement.engagement_id)
    current = versions[-1]
    views = spine_views(session, spine, engagement, [current])
    threshold = current_threshold(session, engagement)
    entries = entries_by_misstatement(session, [misstatement.id])[misstatement.id]
    answer = misstatement_json(
        misstatement,
        current,
        views[current.id],
        threshold,
        settings,
        versions=versions,
        entries=entries,
    )
    answer["transition"] = outcome_json(outcome)
    return answer
