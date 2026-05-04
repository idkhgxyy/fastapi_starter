"""add document ownership and processing status

Revision ID: 5c6f8b7a9d21
Revises: 4d6e1d2b8d10
Create Date: 2026-05-04 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c6f8b7a9d21"
down_revision: Union[str, Sequence[str], None] = "4d6e1d2b8d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("status", sa.String(length=32), server_default="queued", nullable=False))
    op.add_column("documents", sa.Column("chunks_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("processing_task_id", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False))

    op.create_index(op.f("ix_documents_owner_id"), "documents", ["owner_id"], unique=False)
    op.create_index(op.f("ix_documents_processing_task_id"), "documents", ["processing_task_id"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)
    op.create_foreign_key(
        "fk_documents_owner_id_users",
        "documents",
        "users",
        ["owner_id"],
        ["id"],
    )

    op.alter_column("documents", "status", server_default=None)
    op.alter_column("documents", "chunks_count", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_documents_owner_id_users", "documents", type_="foreignkey")
    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_processing_task_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_owner_id"), table_name="documents")

    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "processing_task_id")
    op.drop_column("documents", "chunks_count")
    op.drop_column("documents", "status")
    op.drop_column("documents", "owner_id")
