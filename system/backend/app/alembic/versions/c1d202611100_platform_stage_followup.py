"""Persist platform verification follow-ups separately from repair algorithms.

Revision ID: c1d202611100
Revises: b72f601e9c40
"""

from alembic import op
import sqlalchemy as sa

revision = "c1d202611100"
down_revision = "b72f601e9c40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stage_followup",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_stage_id", sa.Uuid(), nullable=False),
        sa.Column("repair_id", sa.Uuid(), nullable=False),
        sa.Column("suite_id", sa.Uuid(), nullable=False),
        sa.Column("target_stage_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_stage_id"], ["stage_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_stage_id"], ["stage_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stage_followup_source_stage_id", "stage_followup", ["source_stage_id"], unique=True)
    op.create_index("ix_stage_followup_status", "stage_followup", ["status"])


def downgrade():
    op.drop_table("stage_followup")
