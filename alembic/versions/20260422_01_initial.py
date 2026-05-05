"""initial schema

Revision ID: 20260422_01
Revises:
Create Date: 2026-04-22 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260422_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


account_type = postgresql.ENUM("USER", "EMPLOYEE", name="account_type")
facility_status = postgresql.ENUM("ACTIVE", "MAINTENANCE", "INACTIVE", name="facility_status")
equipment_status = postgresql.ENUM("ACTIVE", "WARNING", "OFFLINE", "BROKEN", name="equipment_status")
sensor_status = postgresql.ENUM("ACTIVE", "OFFLINE", "ERROR", name="sensor_status")
sensor_data_status = postgresql.ENUM("NORMAL", "ALERT", "CRITICAL", name="sensor_data_status")
request_status = postgresql.ENUM("CREATED", "IN_PROGRESS", "RESOLVED", "REJECTED", name="request_status")
task_status = postgresql.ENUM("CREATED", "ACTIVE", "COMPLETED", "CANCELLED", name="task_status")
availability_status = postgresql.ENUM("AVAILABLE", "BUSY", "OFFLINE", name="availability_status")
background_job_status = postgresql.ENUM("PENDING", "PROCESSING", "SUCCESS", "FAILED", name="background_job_status")
log_status = postgresql.ENUM("SUCCESS", "FAILED", name="log_status")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_user_id", "users", ["user_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "employees",
        sa.Column("employee_id", sa.Integer(), primary_key=True),
        sa.Column("employee_key", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("middle_name", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("availability_status", availability_status, nullable=False, server_default="AVAILABLE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_key", name="uq_employees_employee_key"),
        sa.UniqueConstraint("email", name="uq_employees_email"),
    )
    op.create_index("ix_employees_employee_id", "employees", ["employee_id"])
    op.create_index("ix_employees_employee_key", "employees", ["employee_key"])
    op.create_index("ix_employees_email", "employees", ["email"])

    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer(), primary_key=True),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("role_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("role_code", name="uq_roles_role_code"),
        sa.UniqueConstraint("role_name", name="uq_roles_role_name"),
    )
    op.create_index("ix_roles_role_id", "roles", ["role_id"])

    op.create_table(
        "sports_facilities",
        sa.Column("facility_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("facility_type", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("opening_date", sa.Date(), nullable=True),
        sa.Column("status", facility_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sports_facilities_facility_id", "sports_facilities", ["facility_id"])
    op.create_index("ix_sports_facilities_status", "sports_facilities", ["status"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "employee_roles",
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.employee_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "equipment",
        sa.Column("equipment_id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("sports_facilities.facility_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("equipment_type", sa.String(length=100), nullable=False),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("status", equipment_status, nullable=False, server_default="ACTIVE"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_equipment_equipment_id", "equipment", ["equipment_id"])
    op.create_index("ix_equipment_facility_id", "equipment", ["facility_id"])
    op.create_index("ix_equipment_status", "equipment", ["status"])

    op.create_table(
        "sensors",
        sa.Column("sensor_id", sa.Integer(), primary_key=True),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.equipment_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sensor_code", sa.String(length=120), nullable=False),
        sa.Column("sensor_type", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("status", sensor_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sensor_code", name="uq_sensors_sensor_code"),
    )
    op.create_index("ix_sensors_sensor_id", "sensors", ["sensor_id"])
    op.create_index("ix_sensors_equipment_id", "sensors", ["equipment_id"])
    op.create_index("ix_sensors_status", "sensors", ["status"])

    op.create_table(
        "sensor_data",
        sa.Column("data_id", sa.Integer(), primary_key=True),
        sa.Column("sensor_id", sa.Integer(), sa.ForeignKey("sensors.sensor_id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("status", sensor_data_status, nullable=False, server_default="NORMAL"),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.Text(), nullable=True),
    )
    op.create_index("ix_sensor_data_data_id", "sensor_data", ["data_id"])
    op.create_index("ix_sensor_data_sensor_id", "sensor_data", ["sensor_id"])
    op.create_index("ix_sensor_data_status", "sensor_data", ["status"])
    op.create_index("ix_sensor_data_measured_at", "sensor_data", ["measured_at"])

    op.create_table(
        "user_requests",
        sa.Column("request_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("sports_facilities.facility_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", request_status, nullable=False, server_default="CREATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_requests_request_id", "user_requests", ["request_id"])
    op.create_index("ix_user_requests_user_id", "user_requests", ["user_id"])
    op.create_index("ix_user_requests_facility_id", "user_requests", ["facility_id"])
    op.create_index("ix_user_requests_status", "user_requests", ["status"])

    op.create_table(
        "engineer_tasks",
        sa.Column("task_id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("sports_facilities.facility_id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("user_requests.request_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_employee_id", sa.Integer(), sa.ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_engineer_id", sa.Integer(), sa.ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("operator_comment", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False, server_default="CREATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("request_id", name="uq_engineer_tasks_request_id"),
    )
    op.create_index("ix_engineer_tasks_task_id", "engineer_tasks", ["task_id"])
    op.create_index("ix_engineer_tasks_facility_id", "engineer_tasks", ["facility_id"])
    op.create_index("ix_engineer_tasks_created_by_employee_id", "engineer_tasks", ["created_by_employee_id"])
    op.create_index("ix_engineer_tasks_assigned_engineer_id", "engineer_tasks", ["assigned_engineer_id"])
    op.create_index("ix_engineer_tasks_status", "engineer_tasks", ["status"])

    op.create_table(
        "engineer_reports",
        sa.Column("report_id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("engineer_tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("engineer_id", sa.Integer(), sa.ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("task_id", name="uq_engineer_reports_task_id"),
    )
    op.create_index("ix_engineer_reports_report_id", "engineer_reports", ["report_id"])
    op.create_index("ix_engineer_reports_engineer_id", "engineer_reports", ["engineer_id"])

    op.create_table(
        "background_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("owner_type", account_type, nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("status", background_job_status, nullable=False, server_default="PENDING"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_background_jobs_job_id", "background_jobs", ["job_id"])
    op.create_index("ix_background_jobs_owner_id", "background_jobs", ["owner_id"])
    op.create_index("ix_background_jobs_owner_type", "background_jobs", ["owner_type"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])

    op.create_table(
        "system_action_log",
        sa.Column("log_id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_employee_id", sa.Integer(), sa.ForeignKey("employees.employee_id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_role", sa.String(length=120), nullable=True),
        sa.Column("action_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("status", log_status, nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(actor_user_id IS NOT NULL AND actor_employee_id IS NULL) OR "
            "(actor_user_id IS NULL AND actor_employee_id IS NOT NULL)",
            name="ck_system_action_log_single_actor",
        ),
    )
    op.create_index("ix_system_action_log_log_id", "system_action_log", ["log_id"])
    op.create_index("ix_system_action_log_actor_user_id", "system_action_log", ["actor_user_id"])
    op.create_index("ix_system_action_log_actor_employee_id", "system_action_log", ["actor_employee_id"])
    op.create_index("ix_system_action_log_action_type", "system_action_log", ["action_type"])
    op.create_index("ix_system_action_log_entity_type", "system_action_log", ["entity_type"])
    op.create_index("ix_system_action_log_entity_id", "system_action_log", ["entity_id"])
    op.create_index("ix_system_action_log_status", "system_action_log", ["status"])


def downgrade() -> None:
    op.drop_index("ix_system_action_log_status", table_name="system_action_log")
    op.drop_index("ix_system_action_log_entity_id", table_name="system_action_log")
    op.drop_index("ix_system_action_log_entity_type", table_name="system_action_log")
    op.drop_index("ix_system_action_log_action_type", table_name="system_action_log")
    op.drop_index("ix_system_action_log_actor_employee_id", table_name="system_action_log")
    op.drop_index("ix_system_action_log_actor_user_id", table_name="system_action_log")
    op.drop_index("ix_system_action_log_log_id", table_name="system_action_log")
    op.drop_table("system_action_log")

    op.drop_index("ix_background_jobs_status", table_name="background_jobs")
    op.drop_index("ix_background_jobs_owner_type", table_name="background_jobs")
    op.drop_index("ix_background_jobs_owner_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_job_id", table_name="background_jobs")
    op.drop_table("background_jobs")

    op.drop_index("ix_engineer_reports_engineer_id", table_name="engineer_reports")
    op.drop_index("ix_engineer_reports_report_id", table_name="engineer_reports")
    op.drop_table("engineer_reports")

    op.drop_index("ix_engineer_tasks_status", table_name="engineer_tasks")
    op.drop_index("ix_engineer_tasks_assigned_engineer_id", table_name="engineer_tasks")
    op.drop_index("ix_engineer_tasks_created_by_employee_id", table_name="engineer_tasks")
    op.drop_index("ix_engineer_tasks_facility_id", table_name="engineer_tasks")
    op.drop_index("ix_engineer_tasks_task_id", table_name="engineer_tasks")
    op.drop_table("engineer_tasks")

    op.drop_index("ix_user_requests_status", table_name="user_requests")
    op.drop_index("ix_user_requests_facility_id", table_name="user_requests")
    op.drop_index("ix_user_requests_user_id", table_name="user_requests")
    op.drop_index("ix_user_requests_request_id", table_name="user_requests")
    op.drop_table("user_requests")

    op.drop_index("ix_sensor_data_measured_at", table_name="sensor_data")
    op.drop_index("ix_sensor_data_status", table_name="sensor_data")
    op.drop_index("ix_sensor_data_sensor_id", table_name="sensor_data")
    op.drop_index("ix_sensor_data_data_id", table_name="sensor_data")
    op.drop_table("sensor_data")

    op.drop_index("ix_sensors_status", table_name="sensors")
    op.drop_index("ix_sensors_equipment_id", table_name="sensors")
    op.drop_index("ix_sensors_sensor_id", table_name="sensors")
    op.drop_table("sensors")

    op.drop_index("ix_equipment_status", table_name="equipment")
    op.drop_index("ix_equipment_facility_id", table_name="equipment")
    op.drop_index("ix_equipment_equipment_id", table_name="equipment")
    op.drop_table("equipment")

    op.drop_table("employee_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_sports_facilities_status", table_name="sports_facilities")
    op.drop_index("ix_sports_facilities_facility_id", table_name="sports_facilities")
    op.drop_table("sports_facilities")

    op.drop_index("ix_roles_role_id", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_employees_email", table_name="employees")
    op.drop_index("ix_employees_employee_key", table_name="employees")
    op.drop_index("ix_employees_employee_id", table_name="employees")
    op.drop_table("employees")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_user_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    log_status.drop(bind, checkfirst=True)
    background_job_status.drop(bind, checkfirst=True)
    availability_status.drop(bind, checkfirst=True)
    task_status.drop(bind, checkfirst=True)
    request_status.drop(bind, checkfirst=True)
    sensor_data_status.drop(bind, checkfirst=True)
    sensor_status.drop(bind, checkfirst=True)
    equipment_status.drop(bind, checkfirst=True)
    facility_status.drop(bind, checkfirst=True)
    account_type.drop(bind, checkfirst=True)
