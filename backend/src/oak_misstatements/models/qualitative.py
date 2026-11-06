"""The qualitative checklist's record (spec sections 5 and 9; architecture D59).

Spec section 9: ``qualitative  misstatement · factor · note · escalated_by · at``. One row is
one entry against one factor of one misstatement. The table is append-only like every other
record here (spec section 3.3: nothing is deleted), so a factor is never updated or removed
in place. Two columns beyond the specification's make that possible:

- ``applies``: true when the entry records the factor (or records it again with a new
  reason), false when it clears it. A cleared factor keeps its history.
- ``entry_no``: the order of the entries of one misstatement, issued under the engagement
  row lock. The factors that apply now are those whose latest entry has ``applies`` true.

``note`` is the recorded reason and is never blank, for a clearing as for a recording.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.core.qualitative import FACTOR_KEYS
from oak_misstatements.db import Base

_LISTED = ", ".join(f"'{key}'" for key in FACTOR_KEYS)


class QualitativeFactor(Base):
    __tablename__ = "qualitative"
    __table_args__ = (
        UniqueConstraint("misstatement_id", "entry_no", name="uq_qualitative_entry"),
        Index("ix_qualitative_misstatement", "misstatement_id"),
        CheckConstraint("entry_no >= 1", name="ck_qualitative_entry_positive"),
        CheckConstraint(f"factor IN ({_LISTED})", name="ck_qualitative_factor"),
        CheckConstraint("length(trim(note)) > 0", name="ck_qualitative_note_not_blank"),
        CheckConstraint("length(trim(escalated_by)) > 0", name="ck_qualitative_escalated_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    misstatement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("misstatement.id", ondelete="RESTRICT")
    )
    entry_no: Mapped[int] = mapped_column(Integer())
    factor: Mapped[str] = mapped_column(Text())
    applies: Mapped[bool] = mapped_column(Boolean())
    note: Mapped[str] = mapped_column(Text())
    escalated_by: Mapped[str] = mapped_column(Text())
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
