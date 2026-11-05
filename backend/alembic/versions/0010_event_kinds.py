"""The event trail accepts only the kinds the module writes (architecture D13, D46).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-05

D13 approved one append-only ``event`` table "with a kind and a JSON payload validated per
kind". Until now the table accepted any non-blank kind. This migration adds the CHECK that
holds the kind to the five the module writes; the payload of each kind is validated by the
application before insert (``models/event.py``). A new kind needs a new migration, which is
the point: an event of an unknown kind cannot be written by anyone.

No existing row is touched. Every row written so far has one of these kinds, because only
the module's own services have ever inserted one. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "threshold_recompute",
    "soft_gate_acknowledged",
    "materiality_reassessed",
    "evaluation_concluded",
    "strategy_trigger_response",
)


def upgrade() -> None:
    listed = ", ".join(f"'{kind}'" for kind in KINDS)
    op.create_check_constraint("ck_event_kind_known", "event", f"kind IN ({listed})")


def downgrade() -> None:
    op.drop_constraint("ck_event_kind_known", "event", type_="check")
