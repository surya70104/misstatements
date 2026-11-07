"""The misstatement record (spec sections 3, 8, 9; architecture D9, D14, D21).

``misstatement`` is the identity: engagement, a reference issued once per engagement and
never reused (D10), who raised it and when. ``misstatement_version`` holds every field that
can change; the current version is the one with the highest ``version_no``. Both are
insert-only for every role (D6, migration 0002). A state move is the next version (Stage 3,
D41): the versions are the state trail, and migration 0007 holds each one to the diagram.

Amounts never live here (spec section 1): ``spine_adjustment_id`` links the version to the
Financial Spine adjustment that holds the Dr/Cr lines, and every effect is computed from
those lines on read. The one exception the spec itself makes is the judgemental range,
which is the auditor's own estimate, not a posted amount (spec 3.2, D14).

``origin`` (Pass 2, D64; migration 0013) carries what spec section 8 says a source attaches
beyond its reference: an agent run's id and source-row citations, a review note's
reference and link. It is null for a working-paper or manual entry, whose ``source_ref``
is the working paper, and is copied unchanged onto every later version.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base

MISSTATEMENT_TYPES = ("factual", "judgemental", "projected")
RAISED_FROM = ("wp", "run", "note", "manual")
# How a projected misstatement was projected from its sample (SA 530; D65). 'other' is
# for a method the list lacks, which the projection basis then describes.
SAMPLING_METHODS = ("ratio", "difference", "mean_per_unit", "monetary_unit", "other")
SAMPLING_FIELDS = (
    "sampling_method",
    "population_value",
    "population_size",
    "sample_value",
    "sample_size",
    "known_error_in_sample",
)
STATES = ("raised", "communicated", "corrected", "refused", "withdrawn")
SPINE_KINDS = ("reclass", "correction")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Misstatement(Base):
    __tablename__ = "misstatement"
    __table_args__ = (
        UniqueConstraint("engagement_id", "ref_no", name="uq_misstatement_engagement_ref"),
        CheckConstraint("ref_no >= 1", name="ck_misstatement_ref_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("engagement.id", ondelete="RESTRICT")
    )
    ref_no: Mapped[int] = mapped_column(Integer())
    created_by: Mapped[str] = mapped_column(Text())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def ref(self) -> str:
        """The reference as the schedule shows it."""
        return f"M-{self.ref_no}"


class MisstatementVersion(Base):
    __tablename__ = "misstatement_version"
    __table_args__ = (
        UniqueConstraint("misstatement_id", "version_no", name="uq_misstatement_version_no"),
        Index("ix_misstatement_version_misstatement", "misstatement_id"),
        CheckConstraint("version_no >= 1", name="ck_misstatement_version_positive"),
        CheckConstraint(_in("type", MISSTATEMENT_TYPES), name="ck_misstatement_version_type"),
        CheckConstraint(_in("raised_from", RAISED_FROM), name="ck_misstatement_version_source"),
        CheckConstraint(_in("state", STATES), name="ck_misstatement_version_state"),
        CheckConstraint(_in("spine_kind", SPINE_KINDS), name="ck_misstatement_version_kind"),
        CheckConstraint(
            "length(trim(description)) > 0", name="ck_misstatement_version_description"
        ),
        CheckConstraint("length(trim(source_ref)) > 0", name="ck_misstatement_version_source_ref"),
        # Spec section 8 (D64): a run or a note carries its origin; a working paper or a manual
        # entry carries none beyond the working paper itself. The shape of the origin is held
        # by migration 0013 on PostgreSQL and by the schema here.
        CheckConstraint(
            "(raised_from IN ('run', 'note')) = (origin IS NOT NULL)",
            name="ck_misstatement_version_origin",
        ),
        # Spec 3.2: a judgemental item carries the range; no other type does (D14).
        CheckConstraint(
            "(type <> 'judgemental') OR "
            "(range_low IS NOT NULL AND range_high IS NOT NULL AND range_low <= range_high)",
            name="ck_misstatement_version_judgemental_range",
        ),
        CheckConstraint(
            "(type = 'judgemental') OR (range_low IS NULL AND range_high IS NULL)",
            name="ck_misstatement_version_range_only_judgemental",
        ),
        # Spec 3.2: a projected item names its sample and projection basis; no other type does.
        CheckConstraint(
            "(type <> 'projected') OR (sample_ref IS NOT NULL AND projection_basis IS NOT NULL)",
            name="ck_misstatement_version_projected_fields",
        ),
        CheckConstraint(
            "(type = 'projected') OR (sample_ref IS NULL AND projection_basis IS NULL)",
            name="ck_misstatement_version_projection_only_projected",
        ),
        # SA 530; spec 3.2 (D65; migration 0015): a projected item says how it was projected
        # from its sample, and no other type does. The projected amount is its lines.
        CheckConstraint(
            "(type <> 'projected') OR ("
            + " AND ".join(f"{field} IS NOT NULL" for field in SAMPLING_FIELDS)
            + ")",
            name="ck_misstatement_version_sampling_present",
        ),
        CheckConstraint(
            "(type = 'projected') OR ("
            + " AND ".join(f"{field} IS NULL" for field in SAMPLING_FIELDS)
            + ")",
            name="ck_misstatement_version_sampling_only_projected",
        ),
        CheckConstraint(
            "sampling_method IS NULL OR " + _in("sampling_method", SAMPLING_METHODS),
            name="ck_misstatement_version_sampling_method",
        ),
        CheckConstraint(
            "(population_size IS NULL AND sample_size IS NULL) OR "
            "(population_size >= 1 AND sample_size >= 1 AND sample_size <= population_size)",
            name="ck_misstatement_version_sampling_sizes",
        ),
        CheckConstraint(
            "(population_value IS NULL AND sample_value IS NULL) OR "
            "(population_value > 0 AND sample_value >= 0 AND sample_value <= population_value)",
            name="ck_misstatement_version_sampling_values",
        ),
        # Spec section 3.3 (D41; migration 0007): the dates and reasons follow the state.
        CheckConstraint(
            "version_no > 1 OR state = 'raised'", name="ck_misstatement_version_first_is_raised"
        ),
        CheckConstraint(
            "(state = 'raised') = (communicated_at IS NULL)",
            name="ck_misstatement_version_communicated_at",
        ),
        CheckConstraint(
            "(state IN ('corrected', 'refused', 'withdrawn')) = (decided_at IS NOT NULL)",
            name="ck_misstatement_version_decided_at",
        ),
        # Acceptance 3: a refusal without a reason is rejected, here too.
        CheckConstraint(
            "(state = 'refused') = (refusal_reason IS NOT NULL) "
            "AND (refusal_reason IS NULL OR length(trim(refusal_reason)) > 0)",
            name="ck_misstatement_version_refusal_reason",
        ),
        CheckConstraint(
            "(state = 'withdrawn') = (withdrawal_reason IS NOT NULL) "
            "AND (withdrawal_reason IS NULL OR length(trim(withdrawal_reason)) > 0)",
            name="ck_misstatement_version_withdrawal_reason",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    misstatement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("misstatement.id", ondelete="RESTRICT")
    )
    version_no: Mapped[int] = mapped_column(Integer())
    type: Mapped[str] = mapped_column(Text())
    description: Mapped[str] = mapped_column(Text())
    raised_by: Mapped[str] = mapped_column(Text())
    raised_from: Mapped[str] = mapped_column(Text())
    source_ref: Mapped[str] = mapped_column(Text())
    origin: Mapped[dict[str, Any] | None] = mapped_column(
        # None is SQL NULL, never the JSON text "null": the CHECK above reads it.
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
    )
    state: Mapped[str] = mapped_column(Text(), server_default="raised")
    communicated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    refusal_reason: Mapped[str | None] = mapped_column(Text())
    withdrawal_reason: Mapped[str | None] = mapped_column(Text())
    # The link: amounts live in the Spine, not here (spec section 9).
    spine_adjustment_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    # The kind the adjustment was proposed as, recorded so the choice is never silent (D23).
    spine_kind: Mapped[str] = mapped_column(Text())
    range_low: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    range_high: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    sample_ref: Mapped[str | None] = mapped_column(Text())
    projection_basis: Mapped[str | None] = mapped_column(Text())
    # SA 530 (D65): how the projection was made. These are the sample's parameters, not
    # the misstatement's amount, which is the lines in the Financial Spine.
    sampling_method: Mapped[str | None] = mapped_column(Text())
    population_value: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    population_size: Mapped[int | None] = mapped_column(Integer())
    sample_value: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    sample_size: Mapped[int | None] = mapped_column(Integer())
    known_error_in_sample: Mapped[Decimal | None] = mapped_column(Numeric(asdecimal=True))
    created_by: Mapped[str] = mapped_column(Text())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
