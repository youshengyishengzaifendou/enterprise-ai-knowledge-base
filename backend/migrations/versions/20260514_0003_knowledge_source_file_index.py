"""knowledge source file index

Revision ID: 20260514_0003
Revises: 20260512_0002
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa

revision = "20260514_0003"
down_revision = "20260512_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("source_file_path", sa.String(length=1000)))
    op.add_column("knowledge_documents", sa.Column("source_file_name", sa.String(length=255)))
    op.add_column("knowledge_documents", sa.Column("source_file_mime_type", sa.String(length=255)))
    op.add_column("knowledge_documents", sa.Column("source_file_size", sa.Integer()))
    op.add_column("knowledge_documents", sa.Column("source_file_storage", sa.String(length=80)))


def downgrade() -> None:
    op.drop_column("knowledge_documents", "source_file_storage")
    op.drop_column("knowledge_documents", "source_file_size")
    op.drop_column("knowledge_documents", "source_file_mime_type")
    op.drop_column("knowledge_documents", "source_file_name")
    op.drop_column("knowledge_documents", "source_file_path")
