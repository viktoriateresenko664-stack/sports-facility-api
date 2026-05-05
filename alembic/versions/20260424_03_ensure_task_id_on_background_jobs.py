"""ensure task_id exists on background_jobs

Revision ID: 20260424_03
Revises: 20260423_02
Create Date: 2026-04-24 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260424_03"
down_revision: Union[str, None] = "20260423_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("background_jobs")}
    if "task_id" not in columns:
        op.add_column("background_jobs", sa.Column("task_id", sa.Integer(), nullable=True))

    indexes = {idx["name"] for idx in inspector.get_indexes("background_jobs")}
    if "ix_background_jobs_task_id" not in indexes:
        op.create_index("ix_background_jobs_task_id", "background_jobs", ["task_id"])

    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("background_jobs")}
    fk_name = "fk_background_jobs_task_id_engineer_tasks"
    if fk_name not in foreign_keys:
        op.create_foreign_key(
            fk_name,
            "background_jobs",
            "engineer_tasks",
            ["task_id"],
            ["task_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("background_jobs")}
    fk_name = "fk_background_jobs_task_id_engineer_tasks"
    if fk_name in foreign_keys:
        op.drop_constraint(fk_name, "background_jobs", type_="foreignkey")

    indexes = {idx["name"] for idx in inspector.get_indexes("background_jobs")}
    if "ix_background_jobs_task_id" in indexes:
        op.drop_index("ix_background_jobs_task_id", table_name="background_jobs")

    columns = {col["name"] for col in inspector.get_columns("background_jobs")}
    if "task_id" in columns:
        op.drop_column("background_jobs", "task_id")

