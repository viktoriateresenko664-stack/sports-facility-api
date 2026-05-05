"""fix facility coordinate mapping by address

Revision ID: 20260503_06
Revises: 20260503_05
Create Date: 2026-05-03 17:12:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260503_06"
down_revision: Union[str, None] = "20260503_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.7070, longitude = 37.7303
        WHERE address ILIKE '%Люблинская%'
        """
    )
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.7088, longitude = 37.9286
        WHERE address ILIKE '%Покровская%'
        """
    )
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.4874, longitude = 37.3080
        WHERE address ILIKE '%Октябрьский пр-т%'
        """
    )
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.7828, longitude = 37.6200
        WHERE address ILIKE '%Олимпийский пр-т%'
        """
    )
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.7639, longitude = 37.4303
        WHERE address ILIKE '%Островная%'
        """
    )
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.7233, longitude = 37.4008
        WHERE address ILIKE '%Толбухина%'
        """
    )
    op.execute(
        """
        UPDATE sports_facilities
        SET latitude = 55.8063, longitude = 37.7809
        WHERE address ILIKE '%Сиреневый%'
        """
    )


def downgrade() -> None:
    # Keep coordinates intact on downgrade to avoid data loss.
    pass
