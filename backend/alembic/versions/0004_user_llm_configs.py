"""add user llm configs

Revision ID: 0004_user_llm_configs
Revises: 0003_analytics_enhancements
Create Date: 2026-06-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_user_llm_configs"
down_revision: Union[str, None] = "0003_analytics_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_llm_configs" in inspector.get_table_names():
        return
    op.create_table(
        "user_llm_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("domain_hint", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_llm_configs_owner_id"), "user_llm_configs", ["owner_id"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_llm_configs" not in inspector.get_table_names():
        return
    op.drop_index(op.f("ix_user_llm_configs_owner_id"), table_name="user_llm_configs")
    op.drop_table("user_llm_configs")
