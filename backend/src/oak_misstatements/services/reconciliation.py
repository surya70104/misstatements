"""A read-only reconciliation with the Financial Spine (architecture D22, D42, D46).

Raising a misstatement proposes an adjustment to the Spine and then writes the record here.
If the record cannot be written (a flush the database refuses, or a commit that fails) the
Spine keeps a proposal that nothing here points to: an **orphan**. The Spine never deletes an
adjustment, so the orphan stays, and while it is proposed the Spine cannot lock the version
(``D:\\CAF\\backend\\src\\oak_spine\\spine\\lock.py``: no adjustment still proposed). Until now
an orphan was named once, in the error and the log, and could not be found again.

This report lists, for the pinned Spine version:

- **orphans**: the Spine's adjustments that carry one of this module's references in
  ``finding_ref`` (``M-<n>``) and that no misstatement version here links to;
- **missing**: misstatements here whose adjustment the Spine does not have on that version;
- **disagreements**: misstatements whose state here and whose adjustment's status in the
  Spine do not match (D41);
- how many adjustments belong to no misstatement of this module at all (another module's,
  or entered in the Spine directly), which are not this module's to judge.

It reads; it never writes, here or in the Spine, and repairs nothing. A person decides what
to do with an orphan, which in the Spine can only be refused.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from oak_misstatements.core.effects import ZERO
from oak_misstatements.core.states import expected_spine_status
from oak_misstatements.errors import NotFound, ServiceUnavailable
from oak_misstatements.models import Engagement, Misstatement, MisstatementVersion
from oak_misstatements.schemas import amount
from oak_misstatements.services.misstatements import current_versions
from oak_misstatements.services.spine_client import SpineAdjustment, SpineClient

OUR_REFERENCE = re.compile(r"M-\d+")


def _adjustment_json(adjustment: SpineAdjustment) -> dict[str, Any]:
    return {
        "adjustment_id": str(adjustment.adjustment_id),
        "finding_ref": adjustment.finding_ref,
        "kind": adjustment.kind,
        "status": adjustment.status,
        "narration": adjustment.narration,
        "working_paper_ref": adjustment.working_paper_ref,
        "proposed_by": adjustment.proposed_by,
        "proposed_at": None
        if adjustment.proposed_at is None
        else adjustment.proposed_at.isoformat(),
        "decision_note": adjustment.decision_note,
        # The Spine's own measure, read now and never stored here.
        "measure": amount(sum((line.dr for line in adjustment.lines), ZERO)),
    }


def _unavailable(status: str, detail: str, engagement: Engagement) -> dict[str, Any]:
    return {
        "engagement_id": str(engagement.id),
        "spine_version_id": (
            None if engagement.spine_version_id is None else str(engagement.spine_version_id)
        ),
        "status": status,
        "detail": detail,
        "clean": None,
        "orphans": None,
        "missing": None,
        "disagreements": None,
        "duplicated_references": None,
        "not_ours": None,
    }


def reconcile(
    session: Session, client: SpineClient | None, engagement: Engagement
) -> dict[str, Any]:
    if client is None:
        return _unavailable("not_configured", "OAK_SPINE_URL is unset", engagement)
    if engagement.spine_version_id is None:
        return _unavailable("unpinned", "no Spine version is pinned", engagement)
    try:
        adjustments = client.adjustments(engagement.spine_version_id)
    except NotFound as absent:
        return _unavailable("missing", str(absent), engagement)
    except ServiceUnavailable as down:
        return _unavailable("unreachable", str(down), engagement)

    # Every version of every misstatement links the same adjustment today; all are read so
    # that a later edit (pending F9) which links a new one cannot make the old one an orphan.
    linked = set(
        session.scalars(
            select(MisstatementVersion.spine_adjustment_id)
            .join(Misstatement, Misstatement.id == MisstatementVersion.misstatement_id)
            .where(Misstatement.engagement_id == engagement.id)
        )
    )
    by_id = {adjustment.adjustment_id: adjustment for adjustment in adjustments}
    ours = [a for a in adjustments if a.finding_ref and OUR_REFERENCE.fullmatch(a.finding_ref)]
    orphans = [a for a in ours if a.adjustment_id not in linked]

    missing: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    for misstatement, version in current_versions(session, engagement):
        adjustment = by_id.get(version.spine_adjustment_id)
        if adjustment is None:
            missing.append(
                {
                    "ref": misstatement.ref,
                    "state": version.state,
                    "spine_adjustment_id": str(version.spine_adjustment_id),
                }
            )
            continue
        expected = expected_spine_status(version.state)
        if adjustment.status != expected:
            disagreements.append(
                {
                    "ref": misstatement.ref,
                    "state": version.state,
                    "expected_adjustment_status": expected,
                    "adjustment_status": adjustment.status,
                    "spine_adjustment_id": str(adjustment.adjustment_id),
                }
            )

    references: dict[str, int] = {}
    for adjustment in ours:
        assert adjustment.finding_ref is not None  # noqa: S101 - filtered above
        references[adjustment.finding_ref] = references.get(adjustment.finding_ref, 0) + 1
    duplicated = sorted(reference for reference, count in references.items() if count > 1)

    return {
        "engagement_id": str(engagement.id),
        "spine_version_id": str(engagement.spine_version_id),
        "status": "ok",
        "detail": None,
        "clean": not (orphans or missing or disagreements),
        "orphans": [_adjustment_json(adjustment) for adjustment in orphans],
        "missing": missing,
        "disagreements": disagreements,
        # A reference the Spine holds more than once: an orphan and the record that
        # replaced it share the reference, because nothing was committed the first time.
        "duplicated_references": duplicated,
        "not_ours": len(adjustments) - len(ours),
        "basis": (
            "read-only: the Spine's adjustments on the pinned version against the links "
            "recorded here; an orphan carries one of this module's references and no record "
            "here links it; nothing is repaired (architecture D46)"
        ),
    }
