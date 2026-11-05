"""The engagement (architecture D8): the module's own id plus the Financial Spine's
engagement and version ids as plain UUID columns, no foreign keys, verified against the
Spine when set. Nothing from the Spine is copied here; its figures are read when needed.

Only the two Spine link columns ever change. Who created the engagement, when, and its label
are frozen at insert by a trigger, and the application role may update the link columns
only (migration 0006, D36); the row is never deleted."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from oak_misstatements.db import Base


class Engagement(Base):
    __tablename__ = "engagement"
    __table_args__ = (
        CheckConstraint("length(trim(label)) > 0", name="ck_engagement_label_not_blank"),
        # A pinned Spine version needs a Spine engagement to belong to.
        CheckConstraint(
            "spine_version_id IS NULL OR spine_engagement_id IS NOT NULL",
            name="ck_engagement_version_needs_engagement",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Text())
    spine_engagement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    spine_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    created_by: Mapped[str] = mapped_column(Text())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
