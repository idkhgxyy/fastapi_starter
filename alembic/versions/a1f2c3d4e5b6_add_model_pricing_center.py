"""add model pricing center and cny cost column

Revision ID: a1f2c3d4e5b6
Revises: b35f62ae79bf
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5b6'
down_revision: Union[str, Sequence[str], None] = 'b35f62ae79bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'model_pricings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('input_price_per_1m', sa.Float(), nullable=False),
        sa.Column('output_price_per_1m', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_pricings_id'), 'model_pricings', ['id'], unique=False)
    op.create_index(
        op.f('ix_model_pricings_model_name'), 'model_pricings', ['model_name'], unique=True
    )

    op.add_column(
        'llm_call_logs',
        sa.Column('estimated_cost_cny', sa.Float(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('llm_call_logs', 'estimated_cost_cny')
    op.drop_index(op.f('ix_model_pricings_model_name'), table_name='model_pricings')
    op.drop_index(op.f('ix_model_pricings_id'), table_name='model_pricings')
    op.drop_table('model_pricings')
