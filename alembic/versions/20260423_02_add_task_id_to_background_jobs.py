"""add task_id to background_jobs

Revision ID: 20260423_02
Revises: 20260422_01
Create Date: 2026-04-23 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260423_02"
down_revision: Union[str, None] = "20260422_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("background_jobs", sa.Column("task_id", sa.Integer(), nullable=True))
    op.create_index("ix_background_jobs_task_id", "background_jobs", ["task_id"])
    op.create_foreign_key(
        "fk_background_jobs_task_id_engineer_tasks",
        "background_jobs",
        "engineer_tasks",
        ["task_id"],
        ["task_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_background_jobs_task_id_engineer_tasks", "background_jobs", type_="foreignkey")
    op.drop_index("ix_background_jobs_task_id", table_name="background_jobs")
    op.drop_column("background_jobs", "task_id")
