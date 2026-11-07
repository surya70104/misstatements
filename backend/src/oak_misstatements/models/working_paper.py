"""A registered working paper: a frozen snapshot of the generated paper (SA 230; spec
section 6 item 5; architecture D66).

One row per export of one engagement, append-only like every other record here. The row
holds the paper's whole content as it was generated, the SHA-256 of its canonical JSON, the
evaluation run it rests on (which must have been current when it was exported), who
exported it and when. The content is never rewritten: a later state of the engagement is a
later paper. ``paper_no`` numbers the papers of an engagement in order.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base


class WorkingPaper(Base):
    __tablename__ = "working_paper"
    __table_args__ = (
        UniqueConstraint("engagement_id", "paper_no", name="uq_working_paper_no"),
        Index("ix_working_paper_engagement", "engagement_id"),
        CheckConstraint("paper_no >= 1", name="ck_working_paper_no_positive"),
        CheckConstraint(
            "length(content_hash) = 64 AND content_hash = lower(content_hash)",
            name="ck_working_paper_hash",
        ),
        CheckConstraint("length(trim(generated_by)) > 0", name="ck_working_paper_generated_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("engagement.id", ondelete="RESTRICT")
    )
    paper_no: Mapped[int] = mapped_column(Integer())
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("evaluation.id", ondelete="RESTRICT")
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    content_hash: Mapped[str] = mapped_column(Text())
    generated_by: Mapped[str] = mapped_column(Text())
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
