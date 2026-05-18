"""knowledge operations v1

Revision ID: 20260518_0008
Revises: 20260515_0007
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "20260518_0008"
down_revision = "20260515_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    document_columns = {column["name"] for column in inspector.get_columns("knowledge_documents")}
    source_file_columns = {column["name"] for column in inspector.get_columns("knowledge_source_files")} if "knowledge_source_files" in table_names else set()

    if "review_status" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("review_status", sa.String(length=50), nullable=False, server_default="approved"))
    if "publication_status" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("publication_status", sa.String(length=50), nullable=False, server_default="published"))
    if "current_version" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"))
    if "reviewed_by" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("reviewed_by", sa.String(length=36)))
    if "reviewed_at" not in document_columns:
        op.add_column("knowledge_documents", sa.Column("reviewed_at", sa.DateTime(timezone=True)))

    if "knowledge_source_files" in table_names:
        if "parse_status" not in source_file_columns:
            op.add_column("knowledge_source_files", sa.Column("parse_status", sa.String(length=50), nullable=False, server_default="parsed"))
        if "parse_error" not in source_file_columns:
            op.add_column("knowledge_source_files", sa.Column("parse_error", sa.Text()))
        if "linked_document_id" not in source_file_columns:
            op.add_column("knowledge_source_files", sa.Column("linked_document_id", sa.String(length=36)))
            op.create_index("ix_knowledge_source_files_linked_document_id", "knowledge_source_files", ["linked_document_id"])

    if "knowledge_document_versions" not in table_names:
        op.create_table(
            "knowledge_document_versions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("summary", sa.Text()),
            sa.Column("content_text", sa.Text(), nullable=False),
            sa.Column("source_file_id", sa.String(length=36)),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("document_id", "version_number", name="uq_knowledge_document_version"),
        )
        op.create_index("ix_knowledge_document_versions_document_id", "knowledge_document_versions", ["document_id"])
        op.create_index("ix_knowledge_document_versions_source_file_id", "knowledge_document_versions", ["source_file_id"])

    if "knowledge_conflict_reports" not in table_names:
        op.create_table(
            "knowledge_conflict_reports",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
            sa.Column("related_document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
            sa.Column("conflict_type", sa.String(length=80), nullable=False, server_default="possible_conflict"),
            sa.Column("detail", sa.Text()),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_knowledge_conflict_reports_document_id", "knowledge_conflict_reports", ["document_id"])
        op.create_index("ix_knowledge_conflict_reports_related_document_id", "knowledge_conflict_reports", ["related_document_id"])

    op.execute("UPDATE knowledge_documents SET review_status = 'approved' WHERE review_status IS NULL OR review_status = ''")
    op.execute("UPDATE knowledge_documents SET publication_status = 'published' WHERE publication_status IS NULL OR publication_status = ''")
    op.execute("UPDATE knowledge_documents SET current_version = 1 WHERE current_version IS NULL OR current_version < 1")
    if "knowledge_source_files" in table_names:
        op.execute("UPDATE knowledge_source_files SET parse_status = 'parsed' WHERE parse_status IS NULL OR parse_status = ''")


def downgrade() -> None:
    op.drop_index("ix_knowledge_conflict_reports_related_document_id", table_name="knowledge_conflict_reports")
    op.drop_index("ix_knowledge_conflict_reports_document_id", table_name="knowledge_conflict_reports")
    op.drop_table("knowledge_conflict_reports")
    op.drop_index("ix_knowledge_document_versions_source_file_id", table_name="knowledge_document_versions")
    op.drop_index("ix_knowledge_document_versions_document_id", table_name="knowledge_document_versions")
    op.drop_table("knowledge_document_versions")
    op.drop_index("ix_knowledge_source_files_linked_document_id", table_name="knowledge_source_files")
    op.drop_column("knowledge_source_files", "linked_document_id")
    op.drop_column("knowledge_source_files", "parse_error")
    op.drop_column("knowledge_source_files", "parse_status")
    op.drop_column("knowledge_documents", "reviewed_at")
    op.drop_column("knowledge_documents", "reviewed_by")
    op.drop_column("knowledge_documents", "current_version")
    op.drop_column("knowledge_documents", "publication_status")
    op.drop_column("knowledge_documents", "review_status")
