"""add embedding model to qa cache

Revision ID: 7e24cc50c124
Revises: e415d0dd6316
Create Date: 2026-10-27 00:41:12.697994

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e24cc50c124"
down_revision: Union[str, Sequence[str], None] = "e415d0dd6316"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "qa_cache_entries",
        sa.Column("embedding_model", sa.String(length=100), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("qa_cache_entries", "embedding_model")
