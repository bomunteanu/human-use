"""add image_artifacts table

Revision ID: a3f9d2e1b4c8
Revises: 75a4022c99b0
Create Date: 2026-03-21 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f9d2e1b4c8"
down_revision: Union[str, Sequence[str], None] = "75a4022c99b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("prompt_a", sa.Text(), nullable=False),
        sa.Column("prompt_b", sa.Text(), nullable=False),
        sa.Column("image_a", sa.LargeBinary(), nullable=False),
        sa.Column("image_b", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("ix_image_artifacts_session_id", "image_artifacts", ["session_id"])
    op.create_index("ix_image_artifacts_order_id", "image_artifacts", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_image_artifacts_order_id", table_name="image_artifacts")
    op.drop_index("ix_image_artifacts_session_id", table_name="image_artifacts")
    op.drop_table("image_artifacts")
