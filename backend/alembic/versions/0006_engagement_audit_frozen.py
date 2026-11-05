"""The engagement row's audit columns are frozen; only its Spine link may change (B9, D36).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04

Migration 0002 granted the application role UPDATE on the whole ``engagement`` row, so a
caller with that role could overwrite ``created_by``, ``created_at`` or ``label``. The only
update the module ever makes is to the two Spine link columns. This migration restricts
both layers: a trigger refuses any other change for every role, DELETE and TRUNCATE are
refused through the append-only function of migration 0001, and the application role's
UPDATE right is narrowed to the two link columns. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINK_ONLY_FUNCTION = """
CREATE FUNCTION oak_misstatements_engagement_link_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'spine_engagement_id' - 'spine_version_id')
       IS DISTINCT FROM (to_jsonb(OLD) - 'spine_engagement_id' - 'spine_version_id')
    THEN
        RAISE EXCEPTION 'engagement %: only the Spine link may change; who created it, when, '
            'and its label are fixed at insert (architecture D36)', OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END
$$
"""

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        REVOKE UPDATE ON engagement FROM oak_misstatements_app;
        GRANT UPDATE (spine_engagement_id, spine_version_id) ON engagement TO oak_misstatements_app;
    END IF;
END
$$
"""

RESTORE_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT UPDATE ON engagement TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(LINK_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_engagement_link_only BEFORE UPDATE ON engagement "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_engagement_link_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_engagement_no_delete BEFORE DELETE ON engagement "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_engagement_no_truncate BEFORE TRUNCATE ON engagement "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute(RESTORE_GRANTS)
    op.execute("DROP TRIGGER IF EXISTS trg_engagement_no_truncate ON engagement")
    op.execute("DROP TRIGGER IF EXISTS trg_engagement_no_delete ON engagement")
    op.execute("DROP TRIGGER IF EXISTS trg_engagement_link_only ON engagement")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_engagement_link_only()")
