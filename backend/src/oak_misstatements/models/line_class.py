"""The classification snapshot of a misstatement version's lines (architecture D32).

When a misstatement is raised, the Financial Spine's answer gives each line its ledger
identity (key and parent chain), and this module gives it a head, a nature, the head's
Schedule III item and a section from the Spine's tree (D31). That classification is what
the effects were computed on. The Spine serves only its *current* map and its *current*
tree, so without a record of its own an old misstatement's effects would change whenever a
ledger was remapped or the tree moved. This table is that record: one row per line, per
misstatement version, append-only, holding labels only. **It never holds an amount.** The
Dr and Cr stay in the Spine and are read live; a line is matched to its snapshot by ledger
key and parent chain, the Spine's own identity for a ledger.
"""

from __future__ import annotations

import datetime as dt
import uuid

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

SECTIONS = ("assets", "liabilities", "equity", "pl_before_tax", "pl_after_tax", "unresolved")


class MisstatementLineClass(Base):
    __tablename__ = "misstatement_line_class"
    __table_args__ = (
        UniqueConstraint("misstatement_version_id", "position", name="uq_line_class_position"),
        Index("ix_line_class_version", "misstatement_version_id"),
        CheckConstraint("position >= 1", name="ck_line_class_position_positive"),
        CheckConstraint("length(trim(ledger_key)) > 0", name="ck_line_class_key_not_blank"),
        CheckConstraint(
            "section IN ('assets', 'liabilities', 'equity', 'pl_before_tax', 'pl_after_tax', "
            "'unresolved')",
            name="ck_line_class_section",
        ),
        CheckConstraint("nature IS NULL OR nature IN ('BS', 'PL')", name="ck_line_class_nature"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    misstatement_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("misstatement_version.id", ondelete="RESTRICT")
    )
    position: Mapped[int] = mapped_column(Integer())  # the line's place in the adjustment
    ledger_key: Mapped[str] = mapped_column(Text())
    ledger_name: Mapped[str] = mapped_column(Text())
    parent_chain: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    head_id: Mapped[str | None] = mapped_column(Text())
    nature: Mapped[str | None] = mapped_column(Text())
    head_item: Mapped[str | None] = mapped_column(Text())  # the head's own Schedule III item
    section: Mapped[str] = mapped_column(Text())
    spine_version_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    tree_version: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
