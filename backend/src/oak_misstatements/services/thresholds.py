"""Thresholds (spec section 4, section 9 ``threshold``; architecture D26, D27, D29, D30).

Setting thresholds inserts the engagement's next version number. If a current version
exists it is superseded: its ``superseded_by`` is set, once, to the new row, and a
``threshold_recompute`` event is written saying that every band now recomputes against the
new version (spec section 9). Bands are never stored, so "recompute" is a property of
reading, not a batch; the event is the record the spec asks for. The history is read by
version number, never by clock (D30).

Each version records the Spine version it was set against, the performance materiality the
Spine showed then, and a status saying what that reading was, so a missing amount never
means two things (D30). Reading a version compares our PM with the Spine's PM on the
**recorded** version now; if the engagement has since been pinned to another version, that
is reported, never silently compared across (D30). Nothing is reconciled (pending B4).

Who may set thresholds is pending decision B9: the acting identity is recorded as
``set_by`` and no authorisation is enforced, and every answer says so (D29).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oak_misstatements.core.banding import Lines
from oak_misstatements.errors import ModuleError, NotFound
from oak_misstatements.models import Engagement, Event, Threshold
from oak_misstatements.schemas import amount
from oak_misstatements.schemas.thresholds import ThresholdIn, ctt_amount
from oak_misstatements.services.authorisation import POLICY
from oak_misstatements.services.spine_client import SpineClient

SpinePmStatus = Literal["available", "not_set", "not_pinned", "not_configured", "unreachable"]
PmCheckState = Literal[
    "match",
    "mismatch",
    "spine_has_no_pm",
    "not_pinned",
    "not_configured",
    "unreachable",
    "pinned_version_changed",
]

# The full notice, with the identity mode, is added by the API layer (D36).
AUTHORISATION = {"enforced": False, "policy": POLICY}
PM_BELOW_OM_NOTE = (
    "enforced: performance materiality is below overall materiality, refused at the request "
    "and by the database constraint ck_threshold_pm_below_om (SA 320 paragraph 9; "
    "architecture D34)"
)


@dataclass(frozen=True)
class SpinePmReading:
    """What the Spine said about PM on one version, or why it could not say."""

    status: SpinePmStatus
    pm: Decimal | None
    detail: str | None


@dataclass(frozen=True)
class PmCheck:
    state: PmCheckState
    our_pm: Decimal
    spine_pm: Decimal | None
    recorded_version_id: uuid.UUID | None
    pinned_version_id: uuid.UUID | None
    detail: str | None


def fraction(value: Decimal) -> str:
    """A declared fraction exactly as declared, with no trailing zeros a store may add."""
    normalised = value.normalize()
    return f"{normalised:f}"


def current_threshold(session: Session, engagement: Engagement) -> Threshold | None:
    return session.scalar(
        select(Threshold).where(
            Threshold.engagement_id == engagement.id, Threshold.superseded_by.is_(None)
        )
    )


def history(session: Session, engagement: Engagement) -> list[Threshold]:
    """Every version, newest first, by version number (D30)."""
    return list(
        session.scalars(
            select(Threshold)
            .where(Threshold.engagement_id == engagement.id)
            .order_by(Threshold.version_no.desc())
        )
    )


def lines_of(threshold: Threshold) -> Lines:
    """The three lines of a threshold version, for banding (D33)."""
    return Lines(ctt=threshold.ctt, pm=threshold.pm, om=threshold.om)


def get_threshold(session: Session, threshold_id: uuid.UUID) -> Threshold:
    threshold = session.get(Threshold, threshold_id)
    if threshold is None:
        raise NotFound(f"no threshold version {threshold_id}")
    return threshold


def read_spine_pm(client: SpineClient | None, version_id: uuid.UUID | None) -> SpinePmReading:
    """The PM the Spine shows for ``version_id`` right now, with a status that says which of
    the five situations this is (D30)."""
    if version_id is None:
        return SpinePmReading("not_pinned", None, "no Spine version is pinned")
    if client is None:
        return SpinePmReading("not_configured", None, "OAK_SPINE_URL is unset")
    try:
        pm = client.version(version_id).performance_materiality
    except ModuleError as failed:
        return SpinePmReading("unreachable", None, str(failed))
    if pm is None:
        return SpinePmReading(
            "not_set", None, "the Spine version carries no performance materiality"
        )
    return SpinePmReading("available", pm, None)


def changes_between(previous: Threshold, current: Threshold) -> dict[str, dict[str, str]]:
    changed: dict[str, dict[str, str]] = {}
    for field in ("om", "pm", "ctt"):
        before, after = getattr(previous, field), getattr(current, field)
        if before != after:
            changed[field] = {"from": amount(before), "to": amount(after)}
    if previous.ctt_fraction != current.ctt_fraction:
        changed["ctt_fraction"] = {
            "from": fraction(previous.ctt_fraction),
            "to": fraction(current.ctt_fraction),
        }
    if previous.basis != current.basis:
        changed["basis"] = {"from": previous.basis, "to": current.basis}
    return changed


def set_threshold(
    session: Session,
    client: SpineClient | None,
    engagement: Engagement,
    body: ThresholdIn,
    *,
    set_by: str,
) -> tuple[Threshold, Event | None]:
    """Insert the next version; supersede the current one, once, and record the recompute.

    The Spine is read **before** the engagement row is locked, so a slow Spine never holds
    the lock (D35). The pin is then checked again under the lock: if another request
    re-pinned the engagement in between, the Spine is read once more, now under the lock,
    so the recorded version and the PM recorded for it always belong together.
    """
    pin_seen = engagement.spine_version_id
    reading = read_spine_pm(client, pin_seen)
    locked = session.execute(
        select(Engagement)
        .where(Engagement.id == engagement.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if locked.spine_version_id != pin_seen:
        pin_seen = locked.spine_version_id
        reading = read_spine_pm(client, pin_seen)
    previous = current_threshold(session, locked)
    highest = session.scalar(
        select(func.max(Threshold.version_no)).where(Threshold.engagement_id == locked.id)
    )
    threshold = Threshold(
        id=uuid.uuid4(),
        engagement_id=locked.id,
        version_no=int(highest or 0) + 1,
        om=body.om,
        pm=body.pm,
        ctt=ctt_amount(body.pm, body.ctt_fraction),
        ctt_fraction=body.ctt_fraction,
        basis=body.basis,
        set_by=set_by,
        spine_version_id=pin_seen,
        spine_pm_at_set=reading.pm,
        spine_pm_status_at_set=reading.status,
    )
    # The old row stops being current before the new one becomes current, so at most one
    # current version exists at every step; the deferred foreign key allows the order (D26).
    if previous is not None:
        previous.superseded_by = threshold.id
        session.flush()
    session.add(threshold)
    session.flush()
    if previous is None:
        return threshold, None
    event = Event(
        engagement_id=engagement.id,
        kind="threshold_recompute",
        actor=set_by,
        payload={
            "previous_threshold_id": str(previous.id),
            "previous_version_no": previous.version_no,
            "current_threshold_id": str(threshold.id),
            "current_version_no": threshold.version_no,
            "changes": changes_between(previous, threshold),
            "bands": "every band recomputes on read against the current version: nothing is "
            "stored, so the next read of any misstatement bands it against this version (D33)",
        },
    )
    session.add(event)
    session.flush()
    return threshold, event


def pm_check(client: SpineClient | None, engagement: Engagement, threshold: Threshold) -> PmCheck:
    """Our PM against the Spine's PM on the version this threshold was set against. A
    disagreement is reported, never resolved (B4). A changed pin is reported, never compared
    across (D30)."""
    recorded = threshold.spine_version_id
    pinned = engagement.spine_version_id
    if pinned != recorded:
        # Whichever way the pin moved (to another version, from none to one, or from one to
        # none), the version this threshold was set against is not the one pinned now.
        was = (
            "when no Spine version was pinned"
            if recorded is None
            else f"against Spine version {recorded}"
        )
        now = "now has no pinned version" if pinned is None else f"is now pinned to {pinned}"
        return PmCheck(
            "pinned_version_changed",
            threshold.pm,
            None,
            recorded,
            pinned,
            f"this threshold version was set {was}; the engagement {now}. Set thresholds "
            "again against the pinned version to compare",
        )
    reading = read_spine_pm(client, recorded)
    if reading.status == "available" and reading.pm is not None:
        if reading.pm == threshold.pm:
            return PmCheck("match", threshold.pm, reading.pm, recorded, pinned, None)
        return PmCheck(
            "mismatch",
            threshold.pm,
            reading.pm,
            recorded,
            pinned,
            f"this module holds PM {amount(threshold.pm)}; the Spine holds "
            f"{amount(reading.pm)} on version {recorded}. Which is right is not decided here "
            "(pending B4)",
        )
    state: PmCheckState = (
        "spine_has_no_pm" if reading.status == "not_set" else cast(PmCheckState, reading.status)
    )
    return PmCheck(state, threshold.pm, None, recorded, pinned, reading.detail)


def events(session: Session, engagement: Engagement) -> list[Event]:
    return list(
        session.scalars(
            select(Event).where(Event.engagement_id == engagement.id).order_by(Event.seq)
        )
    )


def threshold_json(threshold: Threshold, *, check: PmCheck | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(threshold.id),
        "engagement_id": str(threshold.engagement_id),
        "version_no": threshold.version_no,
        "om": amount(threshold.om),
        "pm": amount(threshold.pm),
        "ctt": amount(threshold.ctt),
        "ctt_fraction": fraction(threshold.ctt_fraction),
        "basis": threshold.basis,
        "set_by": threshold.set_by,
        "set_at": threshold.set_at.isoformat(),
        "superseded_by": None if threshold.superseded_by is None else str(threshold.superseded_by),
        "is_current": threshold.is_current,
        "spine": {
            "version_id": (
                None if threshold.spine_version_id is None else str(threshold.spine_version_id)
            ),
            "pm_at_set": (
                None if threshold.spine_pm_at_set is None else amount(threshold.spine_pm_at_set)
            ),
            "pm_status_at_set": threshold.spine_pm_status_at_set,
        },
        "checks": {"pm_below_om": threshold.pm < threshold.om, "note": PM_BELOW_OM_NOTE},
        "authorisation": dict(AUTHORISATION),
    }
    if check is not None:
        body["spine_pm_check"] = {
            "status": check.state,
            "our_pm": amount(check.our_pm),
            "spine_pm": None if check.spine_pm is None else amount(check.spine_pm),
            "recorded_version_id": (
                None if check.recorded_version_id is None else str(check.recorded_version_id)
            ),
            "pinned_version_id": (
                None if check.pinned_version_id is None else str(check.pinned_version_id)
            ),
            "detail": check.detail,
        }
    return body


def event_json(event: Event) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "id": str(event.id),
        "engagement_id": str(event.engagement_id),
        "kind": event.kind,
        "payload": event.payload,
        "actor": event.actor,
        "at": event.at.isoformat(),
    }
