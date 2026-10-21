"""add conversations and messages

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-21 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    op.create_index(
        op.f('ix_conversations_created_at'), 'conversations', ['created_at'], unique=False
    )
    op.create_index(
        op.f('ix_conversations_updated_at'), 'conversations', ['updated_at'], unique=False
    )
    op.create_index(
        'ix_conversations_user_updated', 'conversations', ['user_id', 'updated_at'], unique=False
    )

    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_conversation_messages_id'), 'conversation_messages', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_conversation_messages_conversation_id'),
        'conversation_messages',
        ['conversation_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_conversation_messages_created_at'),
        'conversation_messages',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        'ix_conversation_messages_conv_id',
        'conversation_messages',
        ['conversation_id', 'id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_conversation_messages_conv_id', table_name='conversation_messages')
    op.drop_index(
        op.f('ix_conversation_messages_created_at'), table_name='conversation_messages'
    )
    op.drop_index(
        op.f('ix_conversation_messages_conversation_id'), table_name='conversation_messages'
    )
    op.drop_index(op.f('ix_conversation_messages_id'), table_name='conversation_messages')
    op.drop_table('conversation_messages')

    op.drop_index('ix_conversations_user_updated', table_name='conversations')
    op.drop_index(op.f('ix_conversations_updated_at'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_created_at'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_table('conversations')
