"""analytics enhancements

Revision ID: 0003_analytics_enhancements
Revises: 0002_favorite_items
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_analytics_enhancements"
down_revision: Union[str, None] = "0002_favorite_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "favorite_items" in tables:
        _add_column_if_missing("favorite_items", sa.Column("dataset_id", sa.String(length=36), nullable=True))
        _add_column_if_missing("favorite_items", sa.Column("group_name", sa.String(length=80), nullable=True))
        _add_column_if_missing(
            "favorite_items",
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        )
        _add_column_if_missing(
            "favorite_items",
            sa.Column("snapshot_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        )
        _create_index_if_missing("ix_favorite_items_dataset_id", "favorite_items", ["dataset_id"])
        _create_index_if_missing("ix_favorite_items_group_name", "favorite_items", ["group_name"])

    if "analysis_jobs" in tables:
        _add_column_if_missing(
            "analysis_jobs",
            sa.Column("algorithm_params_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        )
        _add_column_if_missing(
            "analysis_jobs",
            sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        )
        _add_column_if_missing("analysis_jobs", sa.Column("worker_id", sa.String(length=80), nullable=True))
        _add_column_if_missing("analysis_jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))

    if "analysis_workflows" not in tables:
        op.create_table(
            "analysis_workflows",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("owner_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("steps_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_analysis_workflows_owner_id"), "analysis_workflows", ["owner_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "analysis_workflows" in tables:
        op.drop_index(op.f("ix_analysis_workflows_owner_id"), table_name="analysis_workflows")
        op.drop_table("analysis_workflows")
