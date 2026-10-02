"""Store audit timestamps with timezone; preserve LangGraph-managed tables."""
from alembic import op
import sqlalchemy as sa
revision = "95ea71b4213b"
down_revision = "ae78b6f337ae"
branch_labels = None
depends_on = None

def upgrade():
    for name in ["created_at", "updated_at"]:
        op.alter_column("audit_run", name, existing_type=sa.DateTime(),
                        type_=sa.DateTime(timezone=True), existing_nullable=False,
                        postgresql_using=f"{name} AT TIME ZONE 'UTC'")

def downgrade():
    for name in ["created_at", "updated_at"]:
        op.alter_column("audit_run", name, existing_type=sa.DateTime(timezone=True),
                        type_=sa.DateTime(), existing_nullable=False,
                        postgresql_using=f"{name} AT TIME ZONE 'UTC'")
