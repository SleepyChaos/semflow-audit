"""Bind new platform discovery tasks to independent research executions.

Existing stages have no binding and retain their historical executor/checkpoint.
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d202611110"
down_revision = "c1d202611100"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("research_binding",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("executor", sa.String(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("legacy_source_digest", sa.String(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("entity_map", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["stage_id"], ["stage_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("execution_id"))
    op.create_index("ix_research_binding_stage_id", "research_binding", ["stage_id"], unique=True)

    op.create_table("research_audit_binding",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("scout_stage_id", sa.Uuid(), nullable=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("legacy_source_digest", sa.String(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("entity_map", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audit_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scout_stage_id"], ["stage_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("execution_id"))
    op.create_index("ix_research_audit_binding_audit_id", "research_audit_binding", ["audit_id"], unique=True)


def downgrade():
    op.drop_table("research_audit_binding")
    op.drop_table("research_binding")
