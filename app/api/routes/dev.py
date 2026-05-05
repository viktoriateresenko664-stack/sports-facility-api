from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_current_employee, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType
from app.services.fake_sensor_data_service import build_fake_sensor_payload
from app.services.sensor_degradation_service import sensor_degradation_service

router = APIRouter(prefix="/dev", tags=["dev"])


def _ensure_dev_mode() -> None:
    if (not settings.enable_dev_endpoints) or (not settings.debug) or settings.app_env.strip().lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev endpoint is disabled (requires ENABLE_DEV_ENDPOINTS=true, DEBUG=true, non-production env)",
        )


class SensorDegradationUpdateRequest(BaseModel):
    enabled: bool | None = None
    level: int | None = Field(default=None, ge=0, le=100)
    auto_increase: bool | None = None
    step_per_tick: int | None = Field(default=None, ge=1, le=50)
    auto_recover: bool | None = None
    recover_step_per_tick: int | None = Field(default=None, ge=1, le=50)
    recovering: bool | None = None
    model_config = ConfigDict(extra="forbid")


@router.get("/fake-sensor-data", summary="Dev fake sensor data for frontend")
def get_fake_sensor_data(
    randomize: bool = Query(default=False),
    write_to_db: bool = Query(default=False),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> dict:
    _ = employee
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")
    if settings.sensor_source_mode != "fake_only":
        _ensure_dev_mode()
    if write_to_db and "CHIEF_ENGINEER" not in set(principal.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only chief engineer can persist fake data")
    return build_fake_sensor_payload(db, randomize=randomize, write_to_db=write_to_db)


@router.get("/sensor-degradation", summary="Get sensor degradation settings (dev)")
def get_sensor_degradation() -> dict:
    _ensure_dev_mode()
    state = sensor_degradation_service.get_state()
    return {
        "enabled": state.enabled,
        "level": state.level,
        "auto_increase": state.auto_increase,
        "step_per_tick": state.step_per_tick,
        "auto_recover": state.auto_recover,
        "recover_step_per_tick": state.recover_step_per_tick,
        "recovering": state.recovering,
        "active_critical_sensor_id": sensor_degradation_service.active_critical_sensor_id,
    }


@router.post("/sensor-degradation", summary="Set sensor degradation settings (dev)")
def set_sensor_degradation(payload: SensorDegradationUpdateRequest) -> dict:
    _ensure_dev_mode()
    state = sensor_degradation_service.configure(
        enabled=payload.enabled,
        level=payload.level,
        auto_increase=payload.auto_increase,
        step_per_tick=payload.step_per_tick,
        auto_recover=payload.auto_recover,
        recover_step_per_tick=payload.recover_step_per_tick,
        recovering=payload.recovering,
    )
    return {
        "enabled": state.enabled,
        "level": state.level,
        "auto_increase": state.auto_increase,
        "step_per_tick": state.step_per_tick,
        "auto_recover": state.auto_recover,
        "recover_step_per_tick": state.recover_step_per_tick,
        "recovering": state.recovering,
        "active_critical_sensor_id": sensor_degradation_service.active_critical_sensor_id,
    }
