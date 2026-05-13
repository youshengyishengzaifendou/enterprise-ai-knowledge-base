"""support operations

Revision ID: 20260512_0002
Revises: 20260509_0001
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260512_0002"
down_revision = "20260509_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_unanswered_questions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.String(length=36)),
        sa.Column("project_id", sa.String(length=36)),
        sa.Column("user_id", sa.String(length=36)),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="kb_answer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_support_unanswered_questions_customer_id", "support_unanswered_questions", ["customer_id"])
    op.create_index("ix_support_unanswered_questions_project_id", "support_unanswered_questions", ["project_id"])
    op.create_index("ix_support_unanswered_questions_user_id", "support_unanswered_questions", ["user_id"])


def downgrade() -> None:
    op.drop_table("support_unanswered_questions")
