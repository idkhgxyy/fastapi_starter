"""add qa semantic cache table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'qa_cache_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(settings.EMBEDDING_DIMENSION), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('original_cost_cny', sa.Float(), nullable=False, server_default='0'),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_hit_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_qa_cache_entries_id'), 'qa_cache_entries', ['id'], unique=False)
    op.create_index(
        op.f('ix_qa_cache_entries_user_id'), 'qa_cache_entries', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_qa_cache_entries_created_at'), 'qa_cache_entries', ['created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_table('qa_cache_entries')
