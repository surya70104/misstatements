"""The prior-period carry-forward of one engagement (SA 450 paragraph 11(b); spec sections
4.1 and 9; acceptance 5; architecture D61).

Rows are appended, never changed: recording an item, revising its figures and removing it
from the carry-forward are each a new version of that item. The items carried now are those
whose latest version has ``carried`` true.

The four effects of an item are a person's (register B6). What is computed is their sum,
kept apart from the current year's own misstatements and then shown beside and together
with them (``core/prior_period.py``). No gate reads any of it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from oak_misstatements.core import prior_period as core
from oak_misstatements.core.gates import Aggregate
from oak_misstatements.errors import Conflict, NotFound
from oak_misstatements.models import Engagement, Threshold
from oak_misstatements.models.prior_period import PriorPeriodItem
from oak_misstatements.schemas import amount
from oak_misstatements.schemas.prior_period import EffectsIn, PriorPeriodIn

REF_PREFIX = "PY-"


@dataclass(frozen=True)
class Source:
    """A misstatement of another engagement that an item is rolled forward from, with its
    effects as they stand, uncorrected, there. Built by the backend from its own records
    (``services/prior_period_source.py``), never from the request."""

    misstatement_id: uuid.UUID
    description: str
    source_ref: str
    profit: Decimal
    net_assets: Decimal


def _number(ref: str) -> int:
    return int(ref.removeprefix(REF_PREFIX))


def versions(session: Session, engagement: Engagement) -> list[PriorPeriodItem]:
    """Every version of every item of the engagement, by item and then by version."""
    rows = session.scalars(
        select(PriorPeriodItem).where(PriorPeriodItem.engagement_id == engagement.id)
    )
    return sorted(rows, key=lambda row: (_number(row.ref), row.version_no))


def latest(rows: Sequence[PriorPeriodItem]) -> list[PriorPeriodItem]:
    """The latest version of each item, in the order the items were recorded."""
    newest: dict[str, PriorPeriodItem] = {}
    for row in rows:  # by item, oldest version first: a later one replaces an earlier one
        newest[row.ref] = row
    return list(newest.values())


def carried_now(session: Session, engagement: Engagement) -> list[PriorPeriodItem]:
    """The items carried forward now: those whose latest version is carried."""
    return [row for row in latest(versions(session, engagement)) if row.carried]


def as_carried(row: PriorPeriodItem) -> core.Carried:
    return core.Carried(
        ref=row.ref,
        version_no=row.version_no,
        current_profit=row.current_profit,
        current_net_assets=row.current_net_assets,
        cumulative_profit=row.cumulative_profit,
        cumulative_net_assets=row.cumulative_net_assets,
    )


def _current(rows: Sequence[PriorPeriodItem], ref: str) -> PriorPeriodItem:
    """The latest version of the item ``ref``, which must be carried."""
    found = next((row for row in latest(rows) if row.ref == ref), None)
    if found is None:
        raise NotFound(f"no prior-period item {ref} on this engagement")
    if not found.carried:
        raise Conflict(
            f"{ref} is no longer carried forward (version {found.version_no} removed it); "
            "nothing was saved"
        )
    return found


def record(
    session: Session,
    engagement: Engagement,
    body: PriorPeriodIn,
    *,
    actor: str,
    source: Source | None,
) -> PriorPeriodItem:
    """Record a prior-period item: entered by hand, or rolled forward from ``source``.
    ``engagement`` is locked by the caller, so the reference issued belongs to one moment."""
    rows = versions(session, engagement)
    if source is not None:
        already = next(
            (
                row
                for row in latest(rows)
                if row.carried and row.source_misstatement_id == source.misstatement_id
            ),
            None,
        )
        if already is not None:
            raise Conflict(
                f"that misstatement is already carried forward on this engagement as "
                f"{already.ref}; nothing was saved"
            )
    # What the request says wins; a rolled-forward item falls back on its source's.
    description = body.description or (None if source is None else source.description)
    source_ref = body.source_ref or (None if source is None else source.source_ref)
    assert description is not None and source_ref is not None  # noqa: S101 - the schema
    item = PriorPeriodItem(
        id=uuid.uuid4(),
        engagement_id=engagement.id,
        ref=f"{REF_PREFIX}{len({row.ref for row in rows}) + 1}",
        version_no=1,
        carried=True,
        description=description,
        prior_period=body.prior_period,
        source_ref=source_ref,
        source_misstatement_id=None if source is None else source.misstatement_id,
        prior_profit=None if source is None else source.profit,
        prior_net_assets=None if source is None else source.net_assets,
        current_profit=body.current_profit_before_tax,
        current_net_assets=body.current_net_assets,
        cumulative_profit=body.cumulative_profit_before_tax,
        cumulative_net_assets=body.cumulative_net_assets,
        basis=body.basis,
        recorded_by=actor,
    )
    session.add(item)
    session.flush()
    return item


def _next_version(
    session: Session, current: PriorPeriodItem, *, actor: str, **changes: Any
) -> PriorPeriodItem:
    """A new version of an item: everything the current one says, with ``changes``."""
    values: dict[str, Any] = {
        "carried": current.carried,
        "current_profit": current.current_profit,
        "current_net_assets": current.current_net_assets,
        "cumulative_profit": current.cumulative_profit,
        "cumulative_net_assets": current.cumulative_net_assets,
        "basis": current.basis,
    }
    values.update(changes)
    item = PriorPeriodItem(
        id=uuid.uuid4(),
        engagement_id=current.engagement_id,
        ref=current.ref,
        version_no=current.version_no + 1,
        description=current.description,
        prior_period=current.prior_period,
        source_ref=current.source_ref,
        source_misstatement_id=current.source_misstatement_id,
        prior_profit=current.prior_profit,
        prior_net_assets=current.prior_net_assets,
        recorded_by=actor,
        **values,
    )
    session.add(item)
    session.flush()
    return item


def revise(
    session: Session, engagement: Engagement, ref: str, body: EffectsIn, *, actor: str
) -> PriorPeriodItem:
    """Revise a carried item's four effects and their basis: a new version."""
    current = _current(versions(session, engagement), ref)
    unchanged = (
        current.current_profit == body.current_profit_before_tax
        and current.current_net_assets == body.current_net_assets
        and current.cumulative_profit == body.cumulative_profit_before_tax
        and current.cumulative_net_assets == body.cumulative_net_assets
        and current.basis == body.basis
    )
    if unchanged:
        raise Conflict(f"{ref} already states these effects on this basis; nothing was saved")
    return _next_version(
        session,
        current,
        actor=actor,
        current_profit=body.current_profit_before_tax,
        current_net_assets=body.current_net_assets,
        cumulative_profit=body.cumulative_profit_before_tax,
        cumulative_net_assets=body.cumulative_net_assets,
        basis=body.basis,
    )


def remove(
    session: Session, engagement: Engagement, ref: str, *, reason: str, actor: str
) -> PriorPeriodItem:
    """Stop carrying an item forward, with the reason: a new version. Its earlier versions,
    and its figures, stay."""
    current = _current(versions(session, engagement), ref)
    return _next_version(session, current, actor=actor, carried=False, basis=reason)


# ---- what the API answers ---------------------------------------------------------------------


def item_json(row: PriorPeriodItem) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "ref": row.ref,
        "version_no": row.version_no,
        "carried": row.carried,
        "description": row.description,
        "prior_period": row.prior_period,
        "source_ref": row.source_ref,
        "rolled_forward": row.source_misstatement_id is not None,
        "source_misstatement_id": (
            None if row.source_misstatement_id is None else str(row.source_misstatement_id)
        ),
        # Its effects as they stood, uncorrected, where it was rolled forward from.
        "prior": (
            None
            if row.prior_profit is None or row.prior_net_assets is None
            else {
                "profit_before_tax": amount(row.prior_profit),
                "net_assets": amount(row.prior_net_assets),
            }
        ),
        "current_period": {
            "profit_before_tax": amount(row.current_profit),
            "net_assets": amount(row.current_net_assets),
        },
        "cumulative": {
            "profit_before_tax": amount(row.cumulative_profit),
            "net_assets": amount(row.cumulative_net_assets),
        },
        # On a removing version this is the reason it is no longer carried.
        "basis": row.basis,
        "recorded_by": row.recorded_by,
        "at": None if row.at is None else row.at.isoformat(),
    }


def effect_json(effect: core.Effect) -> dict[str, Any]:
    return {
        "profit_before_tax": {
            "gross": amount(effect.profit.gross),
            "net": amount(effect.profit.net),
        },
        "net_assets": {
            "gross": amount(effect.net_assets.gross),
            "net": amount(effect.net_assets.net),
        },
    }


def _totals(rows: Sequence[PriorPeriodItem]) -> dict[core.Basis, core.Effect]:
    carried = [as_carried(row) for row in rows]
    return {basis: core.total(carried, basis) for basis in core.BASES}


def listing_json(engagement: Engagement, rows: Sequence[PriorPeriodItem]) -> dict[str, Any]:
    """The schedule of prior-period items: those carried now with both effects, those
    removed, every version ever recorded, and what the carried ones come to on each basis."""
    newest = latest(rows)
    carried = [row for row in newest if row.carried]
    totals = _totals(carried)
    return {
        "engagement_id": str(engagement.id),
        "items": [item_json(row) for row in carried],
        "removed": [item_json(row) for row in newest if not row.carried],
        "history": [item_json(row) for row in rows],
        "totals": {basis: effect_json(totals[basis]) for basis in core.BASES},
        "basis": core.PRIOR_PERIOD_BASIS,
    }


def _picture(
    carried: Sequence[PriorPeriodItem], aggregate: Aggregate, threshold: Threshold | None
) -> dict[str, Any]:
    """The figures of the carry-forward beside the current year's: the prior-period totals
    on each basis, the current year's aggregate, the two together, and which lines the
    two together reach. Aggregates only."""
    totals = _totals(carried)
    year = core.current_year(aggregate)
    together = {basis: year.plus(totals[basis]) for basis in core.BASES}
    return {
        "totals": {basis: effect_json(totals[basis]) for basis in core.BASES},
        # The current year's own uncorrected misstatements: the aggregate the gates test.
        "current_year": effect_json(year),
        "with_prior_period": {basis: effect_json(together[basis]) for basis in core.BASES},
        # False when an item of the current year could not be aggregated: every figure that
        # includes the current year is then short.
        "complete": aggregate.complete,
        # Information: the measures of each "with prior-period" view at or above a line.
        "reaches": (
            None
            if threshold is None
            else {
                basis: {
                    "pm": list(core.reached(together[basis], threshold.pm)),
                    "om": list(core.reached(together[basis], threshold.om)),
                }
                for basis in core.BASES
            }
        ),
        # No gate of spec section 7 reads these figures (architecture D61).
        "read_by_gates": False,
    }


def labels(carried: Sequence[PriorPeriodItem]) -> list[dict[str, Any]]:
    """The carried items as labels: reference and the version read. A version is never
    changed, so the same labels always mean the same figures."""
    return [{"ref": row.ref, "version_no": row.version_no} for row in carried]


def evaluation_json(
    carried: Sequence[PriorPeriodItem], aggregate: Aggregate, threshold: Threshold | None
) -> dict[str, Any]:
    """What the evaluation shows of the carry-forward (spec section 10.3: "current and
    cumulative with prior-period items"; acceptance 5)."""
    return {
        "items": [item_json(row) for row in carried],
        **_picture(carried, aggregate, threshold),
        "basis": core.PRIOR_PERIOD_BASIS,
    }


def py_carried_json(
    carried: Sequence[PriorPeriodItem], aggregate: Aggregate, threshold: Threshold | None
) -> dict[str, Any]:
    """What an evaluation run records of the carry-forward (spec section 9 ``py_carried``):
    which version of which item it saw, and the aggregates. Never one item's figures: those
    stay in the item's own, unchangeable version."""
    return {"items": labels(carried), **_picture(carried, aggregate, threshold)}
