"""Explicit knowledge collections and embedding configuration identity."""

import sqlalchemy as sa
from alembic import op

revision = "b72f601e9c40"
down_revision = "965a0de5fd52"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "knowledge_chunk",
        sa.Column("corpus", sa.String(), nullable=False, server_default="unclassified"),
    )
    op.add_column("knowledge_chunk", sa.Column("embedding_identity", sa.String()))
    op.create_index("ix_knowledge_chunk_corpus", "knowledge_chunk", ["corpus"])
    # Known provenance, not guessed titles. Mixed teaching guides remain unclassified.
    op.execute("""UPDATE knowledge_chunk SET corpus='rule_example'
        WHERE source LIKE 'codeql-pack:%'
        AND provenance->>'trust'='pinned_codeql_source'""")
    op.execute("""UPDATE knowledge_chunk SET corpus='reference'
        WHERE source LIKE 'codeql-library:%' OR source LIKE 'framework-api:%'""")
    op.alter_column("knowledge_chunk", "corpus", server_default=None)


def downgrade():
    op.drop_index("ix_knowledge_chunk_corpus", table_name="knowledge_chunk")
    op.drop_column("knowledge_chunk", "embedding_identity")
    op.drop_column("knowledge_chunk", "corpus")
