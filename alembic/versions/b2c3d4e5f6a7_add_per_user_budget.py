"""add per-user budget columns

Revision ID: b2c3d4e5f6a7
Revises: a1f2c3d4e5b6
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1f2c3d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('budget_cny', sa.Float(), nullable=True))
    op.add_column(
        'users',
        sa.Column('budget_period', sa.String(length=20), nullable=True, server_default='monthly'),
    )


def downgrade() -> None:
    op.drop_column('users', 'budget_period')
    op.drop_column('users', 'budget_cny')
