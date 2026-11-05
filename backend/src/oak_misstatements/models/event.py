"""The engagement's event trail (architecture D13, D30): one append-only table for the
records the spec asks for but gives no table of their own. Stage 2 writes
``threshold_recompute`` when a threshold version is superseded (spec section 9: "a revision
recomputes every band and records that it did"); ``soft_gate_acknowledged`` when a partner
acknowledges the soft gate on the current figures (D38, D39). Later stages add the
strategy-trigger decision, the materiality reassessment prompt and Spine re-pointing.

Events are ordered by ``seq``, an insertion sequence issued by the database, never by the
clock: two events in one transaction share a timestamp and must still read in the order they
happened (D30). ``id`` stays the stable identifier the API shows."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base

EVENT_KINDS = (
    "threshold_recompute",
    "soft_gate_acknowledged",
    "materiality_reassessed",
    "evaluation_concluded",
    "strategy_trigger_response",
)

# What each kind's payload must carry (D13: "a JSON payload validated per kind"; D46). A
# payload may carry more; it may not carry less. Checked before every insert.
REQUIRED_PAYLOAD: dict[str, frozenset[str]] = {
    "threshold_recompute": frozenset(
        {
            "previous_threshold_id",
            "previous_version_no",
            "current_threshold_id",
            "current_version_no",
            "changes",
            "bands",
        }
    ),
    "soft_gate_acknowledged": frozenset(
        {"threshold_id", "threshold_version_no", "pm", "pm_gate", "fires_on", "figures"}
    ),
    "materiality_reassessed": frozenset(
        {"evaluation_run_id", "run_no", "threshold_id", "threshold_version_no"}
    ),
    "evaluation_concluded": frozenset(
        {
            "evaluation_run_id",
            "run_no",
            "determination",
            "reviewed_run_id",
            "threshold_id",
            "threshold_version_no",
        }
    ),
    "strategy_trigger_response": frozenset(
        {"threshold_id", "threshold_version_no", "line", "fires_on", "figures", "strategy_revised"}
    ),
}


class InvalidEvent(ValueError):
    """An event of an unknown kind, or one whose payload lacks what its kind requires."""


def check_event(kind: str, payload: Any) -> None:
    if kind not in REQUIRED_PAYLOAD:
        raise InvalidEvent(
            f"{kind!r} is not an event kind of this module; the kinds are "
            + ", ".join(EVENT_KINDS)
            + " (architecture D13, D46)"
        )
    if not isinstance(payload, dict):
        raise InvalidEvent(f"the payload of a {kind} event must be an object")
    missing = sorted(REQUIRED_PAYLOAD[kind] - set(payload))
    if missing:
        raise InvalidEvent(
            f"a {kind} event must carry " + ", ".join(missing) + " (architecture D13, D46)"
        )


class Event(Base):
    __tablename__ = "event"
    __table_args__ = (
        CheckConstraint("length(trim(kind)) > 0", name="ck_event_kind_not_blank"),
        # Only the kinds the module writes (D13, D46; migration 0010).
        CheckConstraint(
            "kind IN (" + ", ".join(f"'{kind}'" for kind in EVENT_KINDS) + ")",
            name="ck_event_kind_known",
        ),
        Index("ix_event_engagement", "engagement_id"),
    )

    seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), Identity(always=True), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(), default=uuid.uuid4, unique=True)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("engagement.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(Text())
    payload: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    actor: Mapped[str] = mapped_column(Text())
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@listens_for(Event, "before_insert")
def _validate_before_insert(_mapper: Any, _connection: Any, target: Event) -> None:
    """No event is written with an unknown kind or an incomplete payload, whichever service
    builds it."""
    check_event(target.kind, target.payload)
