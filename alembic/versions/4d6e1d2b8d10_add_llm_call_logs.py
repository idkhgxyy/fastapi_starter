"""add llm call logs

Revision ID: 4d6e1d2b8d10
Revises: 697bb6f9c24d
Create Date: 2026-04-19 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d6e1d2b8d10'
down_revision: Union[str, Sequence[str], None] = '697bb6f9c24d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_call_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('endpoint', sa.String(length=100), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('tool_calls', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0'),
        sa.Column('estimated_cost_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_call_logs_id'), 'llm_call_logs', ['id'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_user_id'), 'llm_call_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_endpoint'), 'llm_call_logs', ['endpoint'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_request_id'), 'llm_call_logs', ['request_id'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_status'), 'llm_call_logs', ['status'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_created_at'), 'llm_call_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_call_logs_created_at'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_status'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_request_id'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_endpoint'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_user_id'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_id'), table_name='llm_call_logs')
    op.drop_table('llm_call_logs')
