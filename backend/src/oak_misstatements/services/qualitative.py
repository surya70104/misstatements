"""The qualitative checklist against a misstatement (spec section 5; acceptance 8; D59).

Entries are appended, never changed: recording a factor, recording it again with a new
reason, and clearing it are each one new row. The factors that apply now are those whose
latest entry records them. A misstatement is escalated while at least one applies.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oak_misstatements.core.qualitative import ESCALATION_BASIS, FACTOR_KEYS, FACTORS, ordered
from oak_misstatements.errors import Conflict, Invalid, NotFound
from oak_misstatements.models import Engagement, Misstatement
from oak_misstatements.models.qualitative import QualitativeFactor


def entries_by_misstatement(
    session: Session, misstatement_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[QualitativeFactor]]:
    """Every entry of the given misstatements, oldest first, in one query."""
    ids = list(misstatement_ids)
    found: dict[uuid.UUID, list[QualitativeFactor]] = {identifier: [] for identifier in ids}
    if not ids:
        return found
    rows = session.scalars(
        select(QualitativeFactor)
        .where(QualitativeFactor.misstatement_id.in_(ids))
        .order_by(QualitativeFactor.misstatement_id, QualitativeFactor.entry_no)
    )
    for row in rows:
        found[row.misstatement_id].append(row)
    return found


def applying(entries: Sequence[QualitativeFactor]) -> dict[str, QualitativeFactor]:
    """The factors that apply now, each with the entry that says so, in checklist order."""
    latest: dict[str, QualitativeFactor] = {}
    for entry in entries:  # oldest first: a later entry replaces an earlier one
        latest[entry.factor] = entry
    return {key: latest[key] for key in FACTOR_KEYS if key in latest and latest[key].applies}


def factors_by_misstatement(
    session: Session, misstatement_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, ...]]:
    """For each misstatement, the factors that apply now. Empty means not escalated."""
    return {
        identifier: ordered(frozenset(applying(entries)))
        for identifier, entries in entries_by_misstatement(session, misstatement_ids).items()
    }


def _locked(session: Session, misstatement_id: uuid.UUID) -> Misstatement:
    """The misstatement, with its engagement's row locked for the rest of the transaction:
    the entry number issued next, and any evaluation computed meanwhile, belong to one
    moment (the lock every other write of the module takes)."""
    misstatement = session.get(Misstatement, misstatement_id)
    if misstatement is None:
        raise NotFound(f"no misstatement {misstatement_id}")
    session.execute(
        select(Engagement.id).where(Engagement.id == misstatement.engagement_id).with_for_update()
    )
    return misstatement


def _append(
    session: Session,
    misstatement: Misstatement,
    *,
    factor: str,
    applies: bool,
    note: str,
    actor: str,
) -> QualitativeFactor:
    highest = session.scalar(
        select(func.max(QualitativeFactor.entry_no)).where(
            QualitativeFactor.misstatement_id == misstatement.id
        )
    )
    entry = QualitativeFactor(
        id=uuid.uuid4(),
        misstatement_id=misstatement.id,
        entry_no=int(highest or 0) + 1,
        factor=factor,
        applies=applies,
        note=note,
        escalated_by=actor,
    )
    session.add(entry)
    session.flush()
    return entry


def record_factor(
    session: Session, misstatement_id: uuid.UUID, *, factor: str, note: str, actor: str
) -> tuple[Misstatement, list[QualitativeFactor]]:
    """Record a factor, or record it again with a new reason. The misstatement is escalated
    from this entry on (spec section 5)."""
    misstatement = _locked(session, misstatement_id)
    entries = entries_by_misstatement(session, [misstatement.id])[misstatement.id]
    current = applying(entries).get(factor)
    if current is not None and current.note == note:
        raise Conflict(
            f"{misstatement.ref}: the factor {factor!r} is already recorded with this reason; "
            "nothing was saved"
        )
    entries.append(
        _append(session, misstatement, factor=factor, applies=True, note=note, actor=actor)
    )
    return misstatement, entries


def clear_factor(
    session: Session, misstatement_id: uuid.UUID, *, factor: str, note: str, actor: str
) -> tuple[Misstatement, list[QualitativeFactor]]:
    """Clear a recorded factor, with the reason. The entries stay; when no factor applies
    any more the misstatement is no longer escalated."""
    if factor not in FACTORS:
        raise Invalid(
            f"{factor!r} is not a factor of the qualitative checklist; the factors are "
            + ", ".join(FACTOR_KEYS)
        )
    misstatement = _locked(session, misstatement_id)
    entries = entries_by_misstatement(session, [misstatement.id])[misstatement.id]
    if factor not in applying(entries):
        raise Conflict(
            f"{misstatement.ref}: the factor {factor!r} is not recorded, so there is nothing "
            "to clear; nothing was saved"
        )
    entries.append(
        _append(session, misstatement, factor=factor, applies=False, note=note, actor=actor)
    )
    return misstatement, entries


def read_checklist(
    session: Session, misstatement_id: uuid.UUID
) -> tuple[Misstatement, list[QualitativeFactor]]:
    misstatement = session.get(Misstatement, misstatement_id)
    if misstatement is None:
        raise NotFound(f"no misstatement {misstatement_id}")
    return misstatement, entries_by_misstatement(session, [misstatement.id])[misstatement.id]


def _entry_json(entry: QualitativeFactor) -> dict[str, Any]:
    return {
        "entry_no": entry.entry_no,
        "factor": entry.factor,
        "applies": entry.applies,
        "note": entry.note,
        "escalated_by": entry.escalated_by,
        "at": None if entry.at is None else entry.at.isoformat(),
    }


def summary_json(entries: Sequence[QualitativeFactor]) -> dict[str, Any]:
    """What a misstatement carries in the schedule: whether it is escalated, and on what."""
    current = applying(entries)
    return {
        "escalated": bool(current),
        "factors": [
            {
                "factor": key,
                "text": FACTORS[key],
                "note": entry.note,
                "escalated_by": entry.escalated_by,
                "at": None if entry.at is None else entry.at.isoformat(),
            }
            for key, entry in current.items()
        ],
    }


def detail_json(entries: Sequence[QualitativeFactor]) -> dict[str, Any]:
    """What a misstatement carries when it is read on its own: the summary the schedule
    shows, and with it the whole checklist (each factor, whether it applies now and why),
    every entry ever made, oldest first, and the basis of escalation."""
    current = applying(entries)
    return {
        **summary_json(entries),
        "escalation_basis": ESCALATION_BASIS,
        "checklist": [
            {
                "factor": key,
                "text": text,
                "applies": key in current,
                "note": current[key].note if key in current else None,
                "escalated_by": current[key].escalated_by if key in current else None,
                "at": (
                    current[key].at.isoformat()
                    if key in current and current[key].at is not None
                    else None
                ),
            }
            for key, text in FACTORS.items()
        ],
        "history": [_entry_json(entry) for entry in entries],
    }


def checklist_json(
    misstatement: Misstatement, entries: Sequence[QualitativeFactor]
) -> dict[str, Any]:
    """The answer to reading the checklist and to every write on it: which misstatement,
    and its checklist as it now stands."""
    return {
        "misstatement_id": str(misstatement.id),
        "ref": misstatement.ref,
        **detail_json(entries),
    }
