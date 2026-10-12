"""Initial migration

Revision ID: 27eb1f4652f3
Revises: 
Create Date: 2026-10-09 13:33:53.765132

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27eb1f4652f3'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Create tokens table
    op.create_table('tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=50), nullable=True),
        sa.Column('expires_in', sa.Integer(), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create runs table (replaces test5)
    op.create_table('runs',
        sa.Column('db_idx', sa.Integer(), nullable=False),
        sa.Column('run_desc', sa.Text(), nullable=True),
        sa.Column('submitted_run', sa.Text(), nullable=True),
        sa.Column('gateway_id', sa.String(length=255), nullable=False),
        sa.Column('creation_time', sa.Integer(), nullable=True),
        sa.Column('user_subject', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('db_idx'),
        sa.UniqueConstraint('gateway_id')
    )


def downgrade() -> None:
    op.drop_table('runs')
    op.drop_table('tokens')
    op.drop_table('users')

