"""The thresholds (spec section 4 and section 9 ``threshold``; architecture D26, D30).

One row per version: overall materiality, performance materiality, the clearly-trivial
threshold with the fraction of PM a person declared for it, the basis, who set it and when.
Versions are numbered per engagement, 1 upwards, unique at the database, and the history is
read in that order (D30). A revision inserts the next number and sets ``superseded_by`` on
the old row, once; nothing else on a row ever changes and nothing is deleted (migration
0003). The current version is the one with ``superseded_by`` null, at most one per
engagement.

Each row also records the Financial Spine version it was set against, the performance
materiality the Spine showed at that moment, and ``spine_pm_status_at_set`` saying what that
reading was: available, not set on the version, not pinned, Spine not configured, or Spine
unreachable. A null amount therefore never stands for two different things (D30).

Two rules live only in PostgreSQL, in migration 0003, because the in-memory stand-in's
floating-point arithmetic cannot evaluate them exactly: the stored ``ctt`` equals
``round(pm * ctt_fraction, 2)`` (the application's own half-up rounding, D27), and a
successor named by ``superseded_by`` belongs to the same engagement. Two orderings are
enforced: CTT is a fraction of PM, so it is below PM (the spec's own words), and PM is below
OM (SA 320 paragraph 9; D34, migration 0005).
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base

SPINE_PM_STATUSES = ("available", "not_set", "not_pinned", "not_configured", "unreachable")


class Threshold(Base):
    __tablename__ = "threshold"
    __table_args__ = (
        UniqueConstraint("engagement_id", "version_no", name="uq_threshold_engagement_version"),
        CheckConstraint("version_no >= 1", name="ck_threshold_version_positive"),
        CheckConstraint("om > 0", name="ck_threshold_om_positive"),
        CheckConstraint("pm > 0", name="ck_threshold_pm_positive"),
        CheckConstraint("ctt > 0", name="ck_threshold_ctt_positive"),
        # Spec section 4: CTT is a declared fraction of PM, so it lies strictly below PM.
        CheckConstraint(
            "ctt_fraction > 0 AND ctt_fraction < 1", name="ck_threshold_ctt_fraction_range"
        ),
        CheckConstraint("ctt < pm", name="ck_threshold_ctt_below_pm"),
        # SA 320 paragraph 9: performance materiality is set at less than materiality for
        # the financial statements as a whole (D34; migration 0005).
        CheckConstraint("pm < om", name="ck_threshold_pm_below_om"),
        CheckConstraint("length(trim(basis)) > 0", name="ck_threshold_basis_not_blank"),
        CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id", name="ck_threshold_not_self"
        ),
        CheckConstraint(
            "spine_pm_status_at_set IN "
            "('available', 'not_set', 'not_pinned', 'not_configured', 'unreachable')",
            name="ck_threshold_spine_pm_status",
        ),
        # The amount is present exactly when the reading was available; "not pinned" means
        # no version was recorded (D30).
        CheckConstraint(
            "(spine_pm_status_at_set = 'available') = (spine_pm_at_set IS NOT NULL)",
            name="ck_threshold_spine_pm_amount_matches_status",
        ),
        CheckConstraint(
            "(spine_pm_status_at_set = 'not_pinned') = (spine_version_id IS NULL)",
            name="ck_threshold_spine_pm_pinned_matches_status",
        ),
        # At most one current version per engagement.
        Index(
            "uq_threshold_current",
            "engagement_id",
            unique=True,
            postgresql_where=text("superseded_by IS NULL"),
            sqlite_where=text("superseded_by IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("engagement.id", ondelete="RESTRICT")
    )
    version_no: Mapped[int] = mapped_column(Integer())
    om: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    pm: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    ctt: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    ctt_fraction: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    basis: Mapped[str] = mapped_column(Text())
    set_by: Mapped[str] = mapped_column(Text())
    set_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Deferred so a supersession can point the old row at the new one before the new row is
    # inserted, which the one-current-per-engagement index requires (D26).
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("threshold.id", ondelete="RESTRICT", deferrable=True, initially="DEFERRED"),
    )
    spine_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    spine_pm_at_set: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    spine_pm_status_at_set: Mapped[str] = mapped_column(Text())

    @property
    def is_current(self) -> bool:
        return self.superseded_by is None
