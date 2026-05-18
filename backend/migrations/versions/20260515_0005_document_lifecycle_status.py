"""document lifecycle status

Revision ID: 20260515_0005
Revises: 20260515_0004
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260515_0005"
down_revision = "20260515_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("parse_status", sa.String(length=50), nullable=False, server_default="parsed"))
    op.add_column("knowledge_documents", sa.Column("parse_error", sa.Text()))
    op.add_column("knowledge_documents", sa.Column("index_status", sa.String(length=50), nullable=False, server_default="indexed"))


def downgrade() -> None:
    op.drop_column("knowledge_documents", "index_status")
    op.drop_column("knowledge_documents", "parse_error")
    op.drop_column("knowledge_documents", "parse_status")
