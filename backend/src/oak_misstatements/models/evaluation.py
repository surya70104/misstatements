"""The evaluation row (spec section 9 ``evaluation``; section 2, paragraphs 10, 11 and 15;
acceptance 4; architecture D43): append-only, one row per evaluation run.

A run records what the evaluation was when it was made: the engagement, the threshold
version it was run against, the four aggregates of spec section 4.1 (gross and net, profit
before tax and net assets), that materiality was reassessed first (SA 450 paragraph 10),
who ran it and when. ``detail`` keeps the rest of the picture as labels and aggregates: the
figures with and without projected items and by type, the reference, version, state and
band of every misstatement the run saw, the gate statuses, and the Spine version.

**What it never holds:** a Dr or a Cr, or the effect of any single misstatement. Those stay
in the Financial Spine and are computed on read (spec section 1). The four aggregates are
the columns the spec's own data model gives this table.

``conclusion``, ``basis`` and ``concluded_by`` are the spec's own columns (Stage 5, D45),
with ``determination``, the "whether" of spec section 6.4. They are null on a run that
concludes nothing. A conclusion is always a **new** row carrying its own figures and
threshold version, so it cannot drift from what it was based on, and no row is ever updated
to receive one.

``py_carried`` is the spec's own column too (Pass 2; D61; migration 0012): what the run
saw of the prior-period items carried forward, as labels (which version of which item)
and aggregates (their totals on each basis, alone and with the current year's). It is
null on a row written before the column existed. The four ``agg_`` columns remain the
current year's aggregate, the one the gates test.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation"
    __table_args__ = (
        UniqueConstraint("engagement_id", "run_no", name="uq_evaluation_engagement_run"),
        Index("ix_evaluation_engagement", "engagement_id"),
        CheckConstraint("run_no >= 1", name="ck_evaluation_run_positive"),
        # A gross aggregate sums sizes, so it is never negative, and a net aggregate can
        # never exceed it in size (spec section 4.1).
        CheckConstraint(
            "agg_gross_pbt >= 0 AND agg_gross_na >= 0", name="ck_evaluation_gross_not_negative"
        ),
        CheckConstraint(
            "abs(agg_net_pbt) <= agg_gross_pbt AND abs(agg_net_na) <= agg_gross_na",
            name="ck_evaluation_net_within_gross",
        ),
        # SA 450 paragraph 10: materiality is reassessed before the evaluation.
        CheckConstraint("materiality_reassessed", name="ck_evaluation_materiality_reassessed"),
        CheckConstraint("length(trim(evaluated_by)) > 0", name="ck_evaluation_evaluated_by"),
        # The conclusion (spec sections 6.4 and 9; acceptance 10; D45; migration 0009): the
        # four columns are all present, the words not blank, or all absent.
        CheckConstraint(
            "(determination IS NULL AND conclusion IS NULL AND basis IS NULL "
            "AND concluded_by IS NULL) OR "
            "(determination IS NOT NULL AND conclusion IS NOT NULL AND basis IS NOT NULL "
            "AND concluded_by IS NOT NULL AND length(trim(conclusion)) > 0 "
            "AND length(trim(basis)) > 0 AND length(trim(concluded_by)) > 0)",
            name="ck_evaluation_conclusion_complete",
        ),
        CheckConstraint(
            "determination IS NULL OR determination IN ('not_material', 'material')",
            name="ck_evaluation_determination",
        ),
        CheckConstraint(
            "concluded_by IS NULL OR concluded_by = evaluated_by",
            name="ck_evaluation_concluded_by_actor",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("engagement.id", ondelete="RESTRICT")
    )
    run_no: Mapped[int] = mapped_column(Integer())
    # The spec's ``threshold_version``: the version every band and gate of this run used.
    threshold_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("threshold.id", ondelete="RESTRICT")
    )
    agg_gross_pbt: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    agg_net_pbt: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    agg_gross_na: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    agg_net_na: Mapped[Decimal] = mapped_column(Numeric(asdecimal=True))
    materiality_reassessed: Mapped[bool] = mapped_column(Boolean())
    detail: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    py_carried: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    evaluated_by: Mapped[str] = mapped_column(Text())
    # The conclusion, on the row that carries its figures (D45). Null on a run that
    # concludes nothing; a conclusion is always a new row, never an update of one.
    determination: Mapped[str | None] = mapped_column(Text())
    conclusion: Mapped[str | None] = mapped_column(Text())
    basis: Mapped[str | None] = mapped_column(Text())
    concluded_by: Mapped[str | None] = mapped_column(Text())
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
