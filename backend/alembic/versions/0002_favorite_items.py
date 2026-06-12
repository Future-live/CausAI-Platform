"""add favorite items

Revision ID: 0002_favorite_items
Revises: 0001_initial
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_favorite_items"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "favorite_items" in inspector.get_table_names():
        return
    op.create_table(
        "favorite_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_favorite_items_kind"), "favorite_items", ["kind"], unique=False)
    op.create_index(op.f("ix_favorite_items_owner_id"), "favorite_items", ["owner_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "favorite_items" not in inspector.get_table_names():
        return
    op.drop_index(op.f("ix_favorite_items_owner_id"), table_name="favorite_items")
    op.drop_index(op.f("ix_favorite_items_kind"), table_name="favorite_items")
    op.drop_table("favorite_items")
