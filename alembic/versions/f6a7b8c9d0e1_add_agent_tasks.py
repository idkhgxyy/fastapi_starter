"""add agent tasks

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-21 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('scope_document_ids', sa.JSON(), nullable=True),
        sa.Column('output_type', sa.String(length=20), nullable=False),
        sa.Column('result_markdown', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_cny', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_tasks_id'), 'agent_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_agent_tasks_user_id'), 'agent_tasks', ['user_id'], unique=False)
    op.create_index(op.f('ix_agent_tasks_status'), 'agent_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_agent_tasks_created_at'), 'agent_tasks', ['created_at'], unique=False)

    op.create_table(
        'agent_task_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_cny', sa.Float(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_task_steps_id'), 'agent_task_steps', ['id'], unique=False)
    op.create_index(
        op.f('ix_agent_task_steps_task_id'), 'agent_task_steps', ['task_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_task_steps_task_id'), table_name='agent_task_steps')
    op.drop_index(op.f('ix_agent_task_steps_id'), table_name='agent_task_steps')
    op.drop_table('agent_task_steps')

    op.drop_index(op.f('ix_agent_tasks_created_at'), table_name='agent_tasks')
    op.drop_index(op.f('ix_agent_tasks_status'), table_name='agent_tasks')
    op.drop_index(op.f('ix_agent_tasks_user_id'), table_name='agent_tasks')
    op.drop_index(op.f('ix_agent_tasks_id'), table_name='agent_tasks')
    op.drop_table('agent_tasks')
