"""add request status values and facility coordinates

Revision ID: 20260503_05
Revises: 20260501_04
Create Date: 2026-05-03 17:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260503_05"
down_revision: Union[str, None] = "20260501_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'ASSIGNED'")
        op.execute("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'IN_WORK'")

    op.execute(
        """
        UPDATE user_requests ur
        SET status = CASE et.status::text
            WHEN 'CREATED' THEN 'ASSIGNED'::request_status
            WHEN 'ACTIVE' THEN 'IN_WORK'::request_status
            WHEN 'COMPLETED' THEN 'COMPLETED'::request_status
            WHEN 'CANCELLED' THEN 'CANCELLED'::request_status
            ELSE ur.status
        END
        FROM engineer_tasks et
        WHERE et.request_id = ur.request_id
        """
    )

    op.add_column("sports_facilities", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("sports_facilities", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_sports_facilities_latitude_range",
        "sports_facilities",
        "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
    )
    op.create_check_constraint(
        "ck_sports_facilities_longitude_range",
        "sports_facilities",
        "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
    )

    op.execute(
        """
        UPDATE sports_facilities
        SET
            latitude = CASE facility_id
                WHEN 1 THEN 55.7070
                WHEN 2 THEN 55.7088
                WHEN 3 THEN 55.4874
                WHEN 4 THEN 55.7828
                WHEN 5 THEN 55.7639
                WHEN 6 THEN 55.7233
                WHEN 7 THEN 55.8063
                ELSE latitude
            END,
            longitude = CASE facility_id
                WHEN 1 THEN 37.7303
                WHEN 2 THEN 37.9286
                WHEN 3 THEN 37.3080
                WHEN 4 THEN 37.6200
                WHEN 5 THEN 37.4303
                WHEN 6 THEN 37.4008
                WHEN 7 THEN 37.7809
                ELSE longitude
            END
        WHERE facility_id BETWEEN 1 AND 7
          AND (latitude IS NULL OR longitude IS NULL)
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_sports_facilities_longitude_range", "sports_facilities", type_="check")
    op.drop_constraint("ck_sports_facilities_latitude_range", "sports_facilities", type_="check")
    op.drop_column("sports_facilities", "longitude")
    op.drop_column("sports_facilities", "latitude")

    op.execute("UPDATE user_requests SET status = 'ACTIVE' WHERE status IN ('ASSIGNED', 'IN_WORK')")
    op.execute("ALTER TABLE user_requests ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE request_status RENAME TO request_status_extended")

    old_enum = postgresql.ENUM("CREATED", "ACTIVE", "COMPLETED", "CANCELLED", name="request_status")
    old_enum.create(op.get_bind(), checkfirst=False)

    op.execute(
        """
        ALTER TABLE user_requests
        ALTER COLUMN status TYPE request_status
        USING status::text::request_status
        """
    )
    op.execute("ALTER TABLE user_requests ALTER COLUMN status SET DEFAULT 'CREATED'")
    op.execute("DROP TYPE request_status_extended")
