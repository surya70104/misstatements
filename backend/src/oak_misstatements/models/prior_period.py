"""A prior-period uncorrected misstatement carried forward (SA 450 paragraph 11(b); spec
section 4.1; acceptance 5; architecture D61).

The specification's data model names only ``py_carried`` on the evaluation row. It does not
say where a carried item is kept, and that is undecided (register B6). This table is where a
person records one: append-only like every other record here, one row per version of one
item of one engagement.

- ``ref`` (``PY-1``, ``PY-2``...) names the item within its engagement; ``version_no`` orders
  its versions. Recording an item is version 1; revising its figures and removing it from
  the carry-forward are each a new version. Nothing is updated or deleted.
- ``carried`` is true while the item is carried forward and false on the version that
  removes it; the item's figures stay on that row, and ``basis`` then holds the reason.
- The four effects are stated by a person, with ``basis`` saying how they were arrived at.
  This module does not compute how a prior period's misstatement affects the current one.
- ``prior_profit`` and ``prior_net_assets`` are the item's effects as they stood,
  uncorrected, in the engagement it is rolled forward from, copied by the backend from its
  own record; with ``source_misstatement_id`` they are all present, or all absent for an
  item entered by hand.

Unlike a misstatement of the current year, a carried item has no adjustment in the Financial
Spine, so its figures are held here. That is a consequence of B6 being open, not a decision
about it.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
)
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base


class PriorPeriodItem(Base):
    __tablename__ = "prior_period"
    __table_args__ = (
        UniqueConstraint("engagement_id", "ref", "version_no", name="uq_prior_period_version"),
        Index("ix_prior_period_engagement", "engagement_id"),
        CheckConstraint("version_no >= 1", name="ck_prior_period_version_positive"),
        CheckConstraint("length(trim(ref)) > 0", name="ck_prior_period_ref"),
        CheckConstraint("length(trim(description)) > 0", name="ck_prior_period_description"),
        CheckConstraint("length(trim(prior_period)) > 0", name="ck_prior_period_period"),
        CheckConstraint("length(trim(source_ref)) > 0", name="ck_prior_period_source_ref"),
        CheckConstraint("length(trim(basis)) > 0", name="ck_prior_period_basis_not_blank"),
        CheckConstraint("length(trim(recorded_by)) > 0", name="ck_prior_period_recorded_by"),
        # Rolled forward from a misstatement of another engagement: the link and both of its
        # effects there, or none of the three.
        CheckConstraint(
            "(source_misstatement_id IS NULL AND prior_profit IS NULL "
            "AND prior_net_assets IS NULL) OR "
            "(source_misstatement_id IS NOT NULL AND prior_profit IS NOT NULL "
            "AND prior_net_assets IS NOT NULL)",
            name="ck_prior_period_source_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("engagement.id", ondelete="RESTRICT")
    )
    ref: Mapped[str] = mapped_column(Text())
    version_no: Mapped[int] = mapped_column(Integer())
    carried: Mapped[bool] = mapped_column(Boolean())
    description: Mapped[str] = mapped_column(Text())
    # The period the misstatement belongs to, in the firm's words ("FY 2025-26").
    prior_period: Mapped[str] = mapped_column(Text())
    # Where it comes from: the prior period's schedule or working paper.
    source_ref: Mapped[str] = mapped_column(Text())
    source_misstatement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("misstatement.id", ondelete="RESTRICT")
    )
    prior_profit: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    prior_net_assets: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    current_profit: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    current_net_assets: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    cumulative_profit: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    cumulative_net_assets: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    # How the effects were arrived at; on a removing version, why it is no longer carried.
    basis: Mapped[str] = mapped_column(Text())
    recorded_by: Mapped[str] = mapped_column(Text())
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
