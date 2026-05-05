"""add domain events and refresh tokens, align request status enum

Revision ID: 20260501_04
Revises: 20260424_03
Create Date: 2026-05-01 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260501_04"
down_revision: Union[str, None] = "20260424_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


domain_event_status = postgresql.ENUM("PENDING", "PROCESSING", "PROCESSED", "FAILED", name="domain_event_status")


def upgrade() -> None:
    op.execute("ALTER TYPE request_status RENAME VALUE 'IN_PROGRESS' TO 'ACTIVE'")
    op.execute("ALTER TYPE request_status RENAME VALUE 'RESOLVED' TO 'COMPLETED'")
    op.execute("ALTER TYPE request_status RENAME VALUE 'REJECTED' TO 'CANCELLED'")

    domain_event_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "domain_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_id", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("PENDING", "PROCESSING", "PROCESSED", "FAILED", name="domain_event_status", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"])
    op.create_index("ix_domain_events_aggregate_type", "domain_events", ["aggregate_type"])
    op.create_index("ix_domain_events_aggregate_id", "domain_events", ["aggregate_id"])
    op.create_index("ix_domain_events_status", "domain_events", ["status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("account_type", postgresql.ENUM(name="account_type", create_type=False), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_token_id", "refresh_tokens", ["token_id"])
    op.create_index("ix_refresh_tokens_subject_id", "refresh_tokens", ["subject_id"])
    op.create_index("ix_refresh_tokens_account_type", "refresh_tokens", ["account_type"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_account_type", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_subject_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_domain_events_status", table_name="domain_events")
    op.drop_index("ix_domain_events_aggregate_id", table_name="domain_events")
    op.drop_index("ix_domain_events_aggregate_type", table_name="domain_events")
    op.drop_index("ix_domain_events_event_type", table_name="domain_events")
    op.drop_table("domain_events")
    domain_event_status.drop(op.get_bind(), checkfirst=True)

    op.execute("ALTER TYPE request_status RENAME VALUE 'ACTIVE' TO 'IN_PROGRESS'")
    op.execute("ALTER TYPE request_status RENAME VALUE 'COMPLETED' TO 'RESOLVED'")
    op.execute("ALTER TYPE request_status RENAME VALUE 'CANCELLED' TO 'REJECTED'")
