"""add brief column to sessions

Revision ID: 75a4022c99b0
Revises: e2b788ce5aac
Create Date: 2026-03-21 14:46:42.013660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '75a4022c99b0'
down_revision: Union[str, Sequence[str], None] = 'e2b788ce5aac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('brief', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'brief')
