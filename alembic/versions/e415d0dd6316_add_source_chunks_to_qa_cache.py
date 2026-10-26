"""add source chunks to qa cache

Revision ID: e415d0dd6316
Revises: f6a7b8c9d0e1
Create Date: 2026-10-26 07:17:51.700477

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e415d0dd6316"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("qa_cache_entries", sa.Column("source_chunks", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("qa_cache_entries", "source_chunks")
