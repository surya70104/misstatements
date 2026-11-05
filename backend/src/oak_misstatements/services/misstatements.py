"""The misstatement record over the Financial Spine (spec sections 1, 3, 8, 9; architecture
D9, D10, D15, D21, D22, D23, D31, D32).

Raising a misstatement: the pinned Spine version must exist and be unlocked; every line is
resolved to its head, nature and section from the Spine's chain and tree; the effects are
computed; the adjustment kind is chosen in ``core/spine_kind.py`` (which refuses a
classification-only item, pending B2); the engagement row is locked and the next reference
reserved; the adjustment is proposed to the Spine with that reference; then the identity
row, version 1 and the **classification snapshot** of the lines are inserted (D32).

Amounts are never stored here. Reading a misstatement fetches its lines from the Spine, so
the Dr and Cr are always the chain's, and computes the effects on the classification
recorded when the version was raised, so a remapped ledger or a moved tree never changes an
old figure silently. The current classification is read too and every difference is
reported as drift; a line that cannot be matched to its snapshot leaves both effects
unresolved rather than guessed.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from oak_misstatements.core.effects import ZERO, Effects, Line, Nature, Section, compute
from oak_misstatements.core.spine_kind import spine_kind_for
from oak_misstatements.errors import Conflict, Invalid, NotFound, ServiceUnavailable
from oak_misstatements.models import (
    Engagement,
    Misstatement,
    MisstatementLineClass,
    MisstatementVersion,
)
from oak_misstatements.schemas.misstatements import LineIn, MisstatementIn
from oak_misstatements.services.engagements import require_spine
from oak_misstatements.services.spine_client import (
    SpineAdjustment,
    SpineClient,
    SpineLedger,
    SpineTree,
    SpineVersion,
)

ViewState = Literal["ok", "not_configured", "unpinned", "missing", "unreachable"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Drift:
    """One line whose classification in the Spine now differs from the snapshot."""

    position: int
    ledger_name: str
    ledger_key: str
    parent_chain: tuple[str, ...]
    snapshot_head_id: str | None
    snapshot_section: Section
    live_head_id: str | None
    live_section: Section


@dataclass(frozen=True)
class Classification:
    """Where the effects' classification came from, and how the Spine's current
    classification compares (D32)."""

    spine_version_at_raise: uuid.UUID | None
    tree_version_at_raise: str | None
    tree_version_now: str | None
    drift: tuple[Drift, ...]
    unmatched: tuple[str, ...]  # live lines with no snapshot line, and the reverse
    effects_on_current: Effects | None  # for comparison only, when drift was found


@dataclass(frozen=True)
class SpineView:
    """What the Spine holds for one misstatement: its adjustment, the lines carrying the
    snapshot classification, the effects computed on it, and the comparison with the
    current classification. ``effects`` is None when the Spine could not be read; the state
    says why."""

    state: ViewState
    detail: str | None
    adjustment: SpineAdjustment | None
    lines: tuple[Line, ...]
    effects: Effects | None
    tree_version_now: str | None = None
    classification: Classification | None = None


def _key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def pinned_version(client: SpineClient, engagement: Engagement) -> SpineVersion:
    if engagement.spine_version_id is None:
        raise Conflict(
            "no Financial Spine version is pinned to this engagement; set the Spine link first"
        )
    return client.version(engagement.spine_version_id)


def resolve_input_lines(
    lines: list[LineIn], ledgers: list[SpineLedger], tree: SpineTree
) -> list[Line]:
    """The request's lines with the head, nature and section the Spine's tree gives each."""
    by_line_no = {ledger.line_no: ledger for ledger in ledgers}
    resolved: list[Line] = []
    for line in lines:
        dr = line.dr if line.dr is not None else ZERO
        cr = line.cr if line.cr is not None else ZERO
        if line.line_no is not None:
            ledger = by_line_no.get(line.line_no)
            if ledger is None:
                raise Invalid(f"line_no {line.line_no} is not a ledger of the pinned Spine version")
            head = ledger.head_id
            nature = ledger.nature or (
                tree.heads[head].nature if head is not None and head in tree.heads else None
            )
            resolved.append(
                Line(
                    ledger.ledger_key,
                    ledger.ledger_name,
                    ledger.parent_chain,
                    head,
                    nature,
                    tree.section(head),
                    dr,
                    cr,
                )
            )
        else:
            head_id = line.head_id or ""
            entry = tree.heads.get(head_id)
            if entry is None or not entry.mappable:
                raise Invalid(f"head {head_id!r} is not a mappable leaf of the Spine's tree")
            name = line.ledger_name or ""
            resolved.append(
                Line(
                    _key(name),
                    name,
                    tuple(line.parent_chain or []),
                    head_id,
                    entry.nature,
                    tree.section(head_id),
                    dr,
                    cr,
                )
            )
    return resolved


def resolve_spine_lines(
    adjustment: SpineAdjustment, ledgers: list[SpineLedger], tree: SpineTree
) -> list[Line]:
    """An adjustment's lines as the Spine serves them, each given the head the Spine gives it
    **now**: the one the line carries (a ledger the import lacks) or the one the client's
    current map gives the ledger."""
    by_key = {(ledger.ledger_key, ledger.parent_chain): ledger for ledger in ledgers}
    resolved: list[Line] = []
    for line in adjustment.lines:
        head = line.head_id
        if head is None:
            ledger = by_key.get((line.ledger_key, line.parent_chain))
            head = ledger.head_id if ledger is not None else None
        nature = tree.heads[head].nature if head is not None and head in tree.heads else None
        resolved.append(
            Line(
                line.ledger_key,
                line.ledger_name,
                line.parent_chain,
                head,
                nature,
                tree.section(head),
                line.dr,
                line.cr,
            )
        )
    return resolved


# ---- the classification snapshot (D32) -----------------------------------------------------


def snapshot_lines(
    session: Session,
    version_id: uuid.UUID,
    lines: Sequence[Line],
    *,
    spine_version_id: uuid.UUID,
    tree: SpineTree,
) -> list[MisstatementLineClass]:
    """Record the classification every line was given, one append-only row per line. Labels
    only: never a Dr or a Cr."""
    rows = [
        MisstatementLineClass(
            misstatement_version_id=version_id,
            position=position,
            ledger_key=line.ledger_key,
            ledger_name=line.ledger_name,
            parent_chain=list(line.parent_chain),
            head_id=line.head_id,
            nature=line.nature,
            head_item=(
                tree.heads[line.head_id].item
                if line.head_id is not None and line.head_id in tree.heads
                else None
            ),
            section=line.section,
            spine_version_id=spine_version_id,
            tree_version=tree.version,
        )
        for position, line in enumerate(lines, start=1)
    ]
    session.add_all(rows)
    session.flush()
    return rows


def snapshot_for(session: Session, version_id: uuid.UUID) -> list[MisstatementLineClass]:
    return list(
        session.scalars(
            select(MisstatementLineClass)
            .where(MisstatementLineClass.misstatement_version_id == version_id)
            .order_by(MisstatementLineClass.position)
        )
    )


def classify_from_snapshot(
    adjustment: SpineAdjustment, snapshot: Sequence[MisstatementLineClass]
) -> tuple[list[Line], tuple[str, ...]]:
    """The Spine's live lines (the amounts) carrying the snapshot's classification (the
    labels), matched by ledger key and parent chain, the Spine's own identity for a ledger.
    A live line with no snapshot line, or a snapshot line with no live line, is unresolved:
    nothing is guessed, and both are named."""
    waiting = {(row.ledger_key, tuple(row.parent_chain)): row for row in snapshot}
    lines: list[Line] = []
    unmatched: list[str] = []
    for live in adjustment.lines:
        row = waiting.pop((live.ledger_key, live.parent_chain), None)
        if row is None:
            unmatched.append(live.ledger_name)
            lines.append(
                Line(
                    live.ledger_key,
                    live.ledger_name,
                    live.parent_chain,
                    None,
                    None,
                    "unresolved",
                    live.dr,
                    live.cr,
                )
            )
            continue
        lines.append(
            Line(
                live.ledger_key,
                live.ledger_name,
                live.parent_chain,
                row.head_id,
                cast(Nature | None, row.nature),
                cast(Section, row.section),
                live.dr,
                live.cr,
            )
        )
    for row in waiting.values():
        unmatched.append(row.ledger_name)
        lines.append(
            Line(
                row.ledger_key,
                row.ledger_name,
                tuple(row.parent_chain),
                row.head_id,
                cast(Nature | None, row.nature),
                "unresolved",
                ZERO,
                ZERO,
            )
        )
    return lines, tuple(unmatched)


def drift_between(snapshot_lines_: Sequence[Line], live_lines: Sequence[Line]) -> tuple[Drift, ...]:
    """Every matched line whose head or section the Spine now gives differently."""
    live_by_key = {(line.ledger_key, line.parent_chain): line for line in live_lines}
    found: list[Drift] = []
    for position, snap in enumerate(snapshot_lines_, start=1):
        live = live_by_key.get((snap.ledger_key, snap.parent_chain))
        if live is None or (
            snap.section == "unresolved" and snap.head_id is None and live.head_id is None
        ):
            continue
        if snap.head_id != live.head_id or snap.section != live.section:
            found.append(
                Drift(
                    position,
                    snap.ledger_name,
                    snap.ledger_key,
                    snap.parent_chain,
                    snap.head_id,
                    snap.section,
                    live.head_id,
                    live.section,
                )
            )
    return tuple(found)


def view_from_snapshot(
    adjustment: SpineAdjustment,
    snapshot: Sequence[MisstatementLineClass],
    ledgers: list[SpineLedger],
    tree: SpineTree,
) -> SpineView:
    """The effects on the recorded classification, the current classification beside it."""
    if not snapshot:
        lines = [
            Line(
                line.ledger_key,
                line.ledger_name,
                line.parent_chain,
                None,
                None,
                "unresolved",
                line.dr,
                line.cr,
            )
            for line in adjustment.lines
        ]
        classification = Classification(
            None, None, tree.version, (), tuple(entry.ledger_name for entry in lines), None
        )
        return SpineView(
            "ok",
            "no classification snapshot exists for this version (architecture D32)",
            adjustment,
            tuple(lines),
            compute(lines),
            tree.version,
            classification,
        )
    lines, unmatched = classify_from_snapshot(adjustment, snapshot)
    live = resolve_spine_lines(adjustment, ledgers, tree)
    drift = drift_between(lines, live)
    classification = Classification(
        spine_version_at_raise=snapshot[0].spine_version_id,
        tree_version_at_raise=snapshot[0].tree_version,
        tree_version_now=tree.version,
        drift=drift,
        unmatched=unmatched,
        effects_on_current=compute(live) if drift or unmatched else None,
    )
    return SpineView(
        "ok", None, adjustment, tuple(lines), compute(lines), tree.version, classification
    )


# ---- raise and read ------------------------------------------------------------------------


def raise_misstatement(
    session: Session,
    client: SpineClient | None,
    engagement: Engagement,
    body: MisstatementIn,
    *,
    raised_by: str,
) -> tuple[Misstatement, MisstatementVersion, SpineView]:
    spine = require_spine(client)
    version = pinned_version(spine, engagement)
    if version.is_locked:
        raise Conflict(
            f"Spine version {version.version_no} ({version.label!r}) is locked; nothing can be "
            "proposed on it. Unlock it in the Spine, which creates a successor, and pin that"
        )
    ledgers = spine.ledgers(version.version_id)
    tree = spine.tree()
    lines = resolve_input_lines(body.lines, ledgers, tree)
    kind = spine_kind_for(compute(lines))

    # Reserve the next reference under a row lock (D10, D22).
    session.execute(
        select(Engagement).where(Engagement.id == engagement.id).with_for_update()
    ).scalar_one()
    highest = session.scalar(
        select(func.max(Misstatement.ref_no)).where(Misstatement.engagement_id == engagement.id)
    )
    ref_no = int(highest or 0) + 1

    adjustment = spine.propose(
        version.version_id,
        kind=kind,
        narration=body.description,
        working_paper_ref=body.source_ref,
        finding_ref=f"M-{ref_no}",
        lines=[line.to_spine() for line in body.lines],
    )
    spine_lines = resolve_spine_lines(adjustment, ledgers, tree)
    misstatement = Misstatement(engagement_id=engagement.id, ref_no=ref_no, created_by=raised_by)
    record = MisstatementVersion(
        version_no=1,
        type=body.type,
        description=body.description,
        raised_by=raised_by,
        raised_from=body.raised_from,
        source_ref=body.source_ref,
        state="raised",
        spine_adjustment_id=adjustment.adjustment_id,
        spine_kind=kind,
        range_low=body.range_low,
        range_high=body.range_high,
        sample_ref=body.sample_ref,
        projection_basis=body.projection_basis,
        created_by=raised_by,
    )
    try:
        session.add(misstatement)
        session.flush()
        record.misstatement_id = misstatement.id
        session.add(record)
        session.flush()
        snapshot_lines(
            session, record.id, spine_lines, spine_version_id=version.version_id, tree=tree
        )
    except SQLAlchemyError as error:
        # The Spine already holds the proposal and cannot delete it (D22): name the orphan
        # and the database's own error, in the answer and in the log, and hide neither.
        cause: BaseException = getattr(error, "orig", None) or error
        logger.error(
            "orphan Spine adjustment %s (proposed as M-%s on version %s): record not written: %s",
            adjustment.adjustment_id,
            ref_no,
            version.version_id,
            cause,
        )
        raise Conflict(
            f"Spine adjustment {adjustment.adjustment_id} was proposed as M-{ref_no} but the "
            f"record could not be written here: {type(cause).__name__}: {cause}. A person must "
            "resolve the orphan in the Spine (architecture D22)"
        ) from error
    classification = Classification(version.version_id, tree.version, tree.version, (), (), None)
    view = SpineView(
        "ok",
        None,
        adjustment,
        tuple(spine_lines),
        compute(spine_lines),
        tree.version,
        classification,
    )
    return misstatement, record, view


def current_versions(
    session: Session, engagement: Engagement
) -> list[tuple[Misstatement, MisstatementVersion]]:
    """Every misstatement of the engagement with its highest-numbered version (D21)."""
    rows = session.execute(
        select(Misstatement, MisstatementVersion)
        .join(MisstatementVersion, MisstatementVersion.misstatement_id == Misstatement.id)
        .where(Misstatement.engagement_id == engagement.id)
        .order_by(Misstatement.ref_no, MisstatementVersion.version_no)
    ).all()
    latest: dict[uuid.UUID, tuple[Misstatement, MisstatementVersion]] = {}
    for misstatement, version in rows:
        latest[misstatement.id] = (misstatement, version)  # ascending order: the last wins
    return list(latest.values())


def get_misstatement(
    session: Session, misstatement_id: uuid.UUID
) -> tuple[Misstatement, list[MisstatementVersion]]:
    misstatement = session.get(Misstatement, misstatement_id)
    if misstatement is None:
        raise NotFound(f"no misstatement {misstatement_id}")
    versions = list(
        session.scalars(
            select(MisstatementVersion)
            .where(MisstatementVersion.misstatement_id == misstatement.id)
            .order_by(MisstatementVersion.version_no)
        )
    )
    return misstatement, versions


def spine_views(
    session: Session,
    client: SpineClient | None,
    engagement: Engagement,
    records: list[MisstatementVersion],
) -> dict[uuid.UUID, SpineView]:
    """The Spine's side of every record, read once per engagement: the version's ledgers,
    the tree and its adjustments. The effects come from each record's own classification
    snapshot (D32). A Spine that cannot be read leaves every view unresolved with the
    reason, never a guessed figure."""
    if not records:
        return {}
    if client is None:
        view = SpineView("not_configured", "OAK_SPINE_URL is unset", None, (), None)
        return {record.id: view for record in records}
    if engagement.spine_version_id is None:
        view = SpineView("unpinned", "no Spine version is pinned", None, (), None)
        return {record.id: view for record in records}
    try:
        ledgers = client.ledgers(engagement.spine_version_id)
        tree = client.tree()
        adjustments = {a.adjustment_id: a for a in client.adjustments(engagement.spine_version_id)}
    except NotFound as missing:
        view = SpineView("missing", str(missing), None, (), None)
        return {record.id: view for record in records}
    except ServiceUnavailable as down:
        view = SpineView("unreachable", str(down), None, (), None)
        return {record.id: view for record in records}
    views: dict[uuid.UUID, SpineView] = {}
    for record in records:
        adjustment = adjustments.get(record.spine_adjustment_id)
        if adjustment is None:
            views[record.id] = SpineView(
                "missing",
                f"the Spine has no adjustment {record.spine_adjustment_id} on the pinned version",
                None,
                (),
                None,
            )
            continue
        views[record.id] = view_from_snapshot(
            adjustment, snapshot_for(session, record.id), ledgers, tree
        )
    return views


def measure(view: SpineView) -> Decimal | None:
    """The gross size of the lines, the debit total, as the Spine measures an item. Shown
    for information only: the band comes from the two effects, never from this (D33)."""
    if view.adjustment is None:
        return None
    return sum((line.dr for line in view.adjustment.lines), ZERO)
