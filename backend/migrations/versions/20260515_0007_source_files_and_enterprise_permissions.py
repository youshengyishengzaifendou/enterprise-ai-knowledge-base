"""source files and enterprise permissions

Revision ID: 20260515_0007
Revises: 20260515_0006
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260515_0007"
down_revision = "20260515_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    document_columns = {column["name"] for column in inspector.get_columns("knowledge_documents")}
    if "source_file_id" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("source_file_id", sa.String(length=36)))
        op.create_index("ix_knowledge_documents_source_file_id", "knowledge_documents", ["source_file_id"])
    if "source_channel" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("source_channel", sa.String(length=50)))
    if "source_external_user_id" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("source_external_user_id", sa.String(length=255)))

    table_names = set(inspector.get_table_names())
    if "knowledge_source_files" not in table_names:
        op.create_table(
            "knowledge_source_files",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_path", sa.String(length=1000), nullable=False),
            sa.Column("mime_type", sa.String(length=255)),
            sa.Column("file_size", sa.Integer()),
            sa.Column("storage", sa.String(length=80)),
            sa.Column("uploaded_by", sa.String(length=36), nullable=False),
            sa.Column("source_channel", sa.String(length=50)),
            sa.Column("source_external_user_id", sa.String(length=255)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_knowledge_source_files_file_path", "knowledge_source_files", ["file_path"])
        op.create_index("ix_knowledge_source_files_uploaded_by", "knowledge_source_files", ["uploaded_by"])
    if "knowledge_source_file_permissions" not in table_names:
        op.create_table(
            "knowledge_source_file_permissions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("source_file_id", sa.String(length=36), sa.ForeignKey("knowledge_source_files.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("access_level", sa.String(length=50), nullable=False, server_default="read"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("source_file_id", "user_id", name="uq_knowledge_source_file_user_permission"),
        )
        op.create_index("ix_knowledge_source_file_permissions_source_file_id", "knowledge_source_file_permissions", ["source_file_id"])
        op.create_index("ix_knowledge_source_file_permissions_user_id", "knowledge_source_file_permissions", ["user_id"])
    if "knowledge_document_groups" not in table_names:
        op.create_table(
            "knowledge_document_groups",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_knowledge_document_groups_name", "knowledge_document_groups", ["name"])
        op.create_index("ix_knowledge_document_groups_created_by", "knowledge_document_groups", ["created_by"])
    if "knowledge_document_group_memberships" not in table_names:
        op.create_table(
            "knowledge_document_group_memberships",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("group_id", sa.String(length=36), sa.ForeignKey("knowledge_document_groups.id"), nullable=False),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("group_id", "document_id", name="uq_knowledge_group_document"),
        )
        op.create_index("ix_knowledge_document_group_memberships_group_id", "knowledge_document_group_memberships", ["group_id"])
        op.create_index("ix_knowledge_document_group_memberships_document_id", "knowledge_document_group_memberships", ["document_id"])
    if "knowledge_project_permissions" not in table_names:
        op.create_table(
            "knowledge_project_permissions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("access_level", sa.String(length=50), nullable=False, server_default="read"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "user_id", name="uq_knowledge_project_user_permission"),
        )
        op.create_index("ix_knowledge_project_permissions_project_id", "knowledge_project_permissions", ["project_id"])
        op.create_index("ix_knowledge_project_permissions_user_id", "knowledge_project_permissions", ["user_id"])


def downgrade() -> None:
    op.drop_table("knowledge_project_permissions")
    op.drop_table("knowledge_document_group_memberships")
    op.drop_table("knowledge_document_groups")
    op.drop_table("knowledge_source_file_permissions")
    op.drop_table("knowledge_source_files")
    op.drop_column("knowledge_documents", "source_external_user_id")
    op.drop_column("knowledge_documents", "source_channel")
    op.drop_index("ix_knowledge_documents_source_file_id", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "source_file_id")
