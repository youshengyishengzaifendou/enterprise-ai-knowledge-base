"""knowledge access policies

Revision ID: 20260515_0006
Revises: 20260515_0005
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260515_0006"
down_revision = "20260515_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "knowledge_access_policy" not in user_columns:
        op.add_column("users", sa.Column("knowledge_access_policy", sa.String(length=50), nullable=False, server_default="own"))

    if "knowledge_document_permissions" not in inspector.get_table_names():
        op.create_table(
            "knowledge_document_permissions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("access_level", sa.String(length=50), nullable=False, server_default="read"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("document_id", "user_id", name="uq_knowledge_document_user_permission"),
        )
    indexes = {index["name"] for index in inspector.get_indexes("knowledge_document_permissions")}
    if "ix_knowledge_document_permissions_document_id" not in indexes:
        op.create_index("ix_knowledge_document_permissions_document_id", "knowledge_document_permissions", ["document_id"])
    if "ix_knowledge_document_permissions_user_id" not in indexes:
        op.create_index("ix_knowledge_document_permissions_user_id", "knowledge_document_permissions", ["user_id"])
    op.execute("UPDATE users SET knowledge_access_policy = 'all' WHERE id = 'user-demo'")


def downgrade() -> None:
    op.drop_index("ix_knowledge_document_permissions_user_id", table_name="knowledge_document_permissions")
    op.drop_index("ix_knowledge_document_permissions_document_id", table_name="knowledge_document_permissions")
    op.drop_table("knowledge_document_permissions")
    op.drop_column("users", "knowledge_access_policy")
