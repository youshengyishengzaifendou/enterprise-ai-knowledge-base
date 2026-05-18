"""chunk hybrid retrieval index

Revision ID: 20260515_0004
Revises: 20260514_0003
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260515_0004"
down_revision = "20260514_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("embedding_model", sa.String(length=80)))
    op.add_column("knowledge_chunks", sa.Column("embedding_json", sa.Text()))
    op.add_column("knowledge_chunks", sa.Column("index_status", sa.String(length=50), nullable=False, server_default="not_indexed"))
    op.add_column("knowledge_chunks", sa.Column("token_count", sa.Integer()))
    op.add_column("knowledge_chunks", sa.Column("indexed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "indexed_at")
    op.drop_column("knowledge_chunks", "token_count")
    op.drop_column("knowledge_chunks", "index_status")
    op.drop_column("knowledge_chunks", "embedding_json")
    op.drop_column("knowledge_chunks", "embedding_model")
