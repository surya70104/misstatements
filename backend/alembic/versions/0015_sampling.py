"""What a projected misstatement says about its sample (SA 530; SA 450 paragraph A3; spec
section 3.2; architecture D65).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-07

Six nullable columns on ``misstatement_version``, present on a projected item and absent on
every other: the sampling method, the population's value and size, the sample's value and
size, and the misstatement found in the sample. The projected amount itself is not a
column: it is the Dr/Cr lines proposed to the Financial Spine, as every amount is (spec
section 1), and the request is refused when the two differ. Money columns take the domain
of 0001. No row is touched; the rules hold every row written from now on, and every
existing row satisfies them (none is projected without them, since none exists).
This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

METHODS = ("ratio", "difference", "mean_per_unit", "monetary_unit", "other")
MONEY = ("population_value", "sample_value", "known_error_in_sample")
ALL = (
    "sampling_method",
    "population_value",
    "population_size",
    "sample_value",
    "sample_size",
    "known_error_in_sample",
)


def upgrade() -> None:
    op.add_column("misstatement_version", sa.Column("sampling_method", sa.Text(), nullable=True))
    op.add_column(
        "misstatement_version", sa.Column("population_value", sa.Numeric(), nullable=True)
    )
    op.add_column("misstatement_version", sa.Column("population_size", sa.Integer(), nullable=True))
    op.add_column("misstatement_version", sa.Column("sample_value", sa.Numeric(), nullable=True))
    op.add_column("misstatement_version", sa.Column("sample_size", sa.Integer(), nullable=True))
    op.add_column(
        "misstatement_version", sa.Column("known_error_in_sample", sa.Numeric(), nullable=True)
    )
    for column in MONEY:
        op.execute(f"ALTER TABLE misstatement_version ALTER COLUMN {column} TYPE money_amount")
    listed = ", ".join(f"'{method}'" for method in METHODS)
    present = " AND ".join(f"{column} IS NOT NULL" for column in ALL)
    absent = " AND ".join(f"{column} IS NULL" for column in ALL)
    op.create_check_constraint(
        "ck_misstatement_version_sampling_present",
        "misstatement_version",
        f"(type <> 'projected') OR ({present})",
    )
    op.create_check_constraint(
        "ck_misstatement_version_sampling_only_projected",
        "misstatement_version",
        f"(type = 'projected') OR ({absent})",
    )
    op.create_check_constraint(
        "ck_misstatement_version_sampling_method",
        "misstatement_version",
        f"sampling_method IS NULL OR sampling_method IN ({listed})",
    )
    op.create_check_constraint(
        "ck_misstatement_version_sampling_sizes",
        "misstatement_version",
        "(population_size IS NULL AND sample_size IS NULL) OR "
        "(population_size >= 1 AND sample_size >= 1 AND sample_size <= population_size)",
    )
    op.create_check_constraint(
        "ck_misstatement_version_sampling_values",
        "misstatement_version",
        "(population_value IS NULL AND sample_value IS NULL) OR "
        "(population_value > 0 AND sample_value >= 0 AND sample_value <= population_value)",
    )


def downgrade() -> None:
    for name in (
        "ck_misstatement_version_sampling_values",
        "ck_misstatement_version_sampling_sizes",
        "ck_misstatement_version_sampling_method",
        "ck_misstatement_version_sampling_only_projected",
        "ck_misstatement_version_sampling_present",
    ):
        op.drop_constraint(name, "misstatement_version")
    for column in reversed(ALL):
        op.drop_column("misstatement_version", column)
