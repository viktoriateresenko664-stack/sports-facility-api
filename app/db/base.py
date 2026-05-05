from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Alembic autogenerate sees them.
from app.models import (  # noqa: E402,F401
    background_job,
    domain_event,
    employee,
    engineer_report,
    engineer_task,
    equipment,
    refresh_token,
    role,
    sensor,
    sensor_data,
    sports_facility,
    system_action_log,
    user,
    user_request,
)
