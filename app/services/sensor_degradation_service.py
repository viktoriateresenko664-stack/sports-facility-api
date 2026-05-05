from __future__ import annotations

import random
from dataclasses import dataclass
from threading import Lock

from app.core.config import settings


@dataclass
class SensorDegradationState:
    enabled: bool = False
    level: int = 0  # 0..100
    auto_increase: bool = False
    step_per_tick: int = 5
    auto_recover: bool = True
    recover_step_per_tick: int = 10
    recovering: bool = False


class SensorDegradationService:
    def __init__(self) -> None:
        self._state = SensorDegradationState()
        self._voltage_fault_side_by_sensor: dict[str, int] = {}
        self._single_critical_mode = settings.sensor_source_mode == "fake_only"
        self._active_critical_sensor_id: int | None = None
        self._sensor_cycle: list[int] = []
        self._sensor_facility_by_id: dict[int, int | None] = {}
        self._sensor_type_by_id: dict[int, str] = {}
        self._last_value_by_sensor: dict[int, float] = {}
        self._pending_rotate_facility_id: int | None = None
        self._lock = Lock()

    def get_state(self) -> SensorDegradationState:
        return self._state

    def configure(
        self,
        *,
        enabled: bool | None = None,
        level: int | None = None,
        auto_increase: bool | None = None,
        step_per_tick: int | None = None,
        auto_recover: bool | None = None,
        recover_step_per_tick: int | None = None,
        recovering: bool | None = None,
    ) -> SensorDegradationState:
        if enabled is not None:
            self._state.enabled = enabled
        if level is not None:
            self._state.level = max(0, min(100, int(level)))
        if auto_increase is not None:
            self._state.auto_increase = auto_increase
        if step_per_tick is not None:
            self._state.step_per_tick = max(1, min(50, int(step_per_tick)))
        if auto_recover is not None:
            self._state.auto_recover = auto_recover
        if recover_step_per_tick is not None:
            self._state.recover_step_per_tick = max(1, min(50, int(recover_step_per_tick)))
        if recovering is not None:
            self._state.recovering = recovering

        if enabled is True:
            self._state.recovering = False
        elif enabled is False and self._state.level > 0 and self._state.auto_recover:
            self._state.recovering = True

        if self._state.level <= 0:
            self._state.recovering = False
        return self._state

    def start_recovery(self) -> SensorDegradationState:
        self._state.enabled = False
        self._state.auto_increase = False
        self._state.recovering = self._state.level > 0
        return self._state

    def reset(self) -> SensorDegradationState:
        self._state.enabled = False
        self._state.level = 0
        self._state.auto_increase = False
        self._state.recovering = False
        self._voltage_fault_side_by_sensor.clear()
        with self._lock:
            self._active_critical_sensor_id = None
            self._sensor_cycle.clear()
            self._sensor_facility_by_id.clear()
            self._sensor_type_by_id.clear()
            self._last_value_by_sensor.clear()
            self._pending_rotate_facility_id = None
        return self._state

    def tick(self) -> SensorDegradationState:
        if self._state.enabled and self._state.auto_increase:
            self._state.level = min(100, self._state.level + self._state.step_per_tick)
            self._state.recovering = False
        elif (not self._state.enabled) and self._state.auto_recover and self._state.level > 0:
            self._state.level = max(0, self._state.level - self._state.recover_step_per_tick)
            self._state.recovering = self._state.level > 0
        if self._state.level <= 0:
            self._state.recovering = False
        return self._state

    @staticmethod
    def _noise(scale: float) -> float:
        return random.uniform(-scale, scale)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _voltage_fault_side(self, sensor_key: str) -> int:
        side = self._voltage_fault_side_by_sensor.get(sensor_key)
        if side is not None:
            return side
        side = 1 if random.random() >= 0.5 else -1
        self._voltage_fault_side_by_sensor[sensor_key] = side
        return side

    @property
    def active_critical_sensor_id(self) -> int | None:
        return self._active_critical_sensor_id

    def sync_sensor_catalog(self, sensor_entries: list[tuple[int, int | None, str | None]]) -> None:
        if not sensor_entries:
            with self._lock:
                self._sensor_cycle.clear()
                self._sensor_facility_by_id.clear()
                self._sensor_type_by_id.clear()
                self._active_critical_sensor_id = None
            return
        with self._lock:
            ordered_sensor_ids = [int(sensor_id) for sensor_id, _facility_id, _sensor_type in sensor_entries]
            self._sensor_cycle = ordered_sensor_ids
            self._sensor_facility_by_id = {
                int(sensor_id): (int(facility_id) if facility_id is not None else None)
                for sensor_id, facility_id, _sensor_type in sensor_entries
            }
            self._sensor_type_by_id = {
                int(sensor_id): str(sensor_type or "")
                for sensor_id, _facility_id, sensor_type in sensor_entries
            }
            active = self._active_critical_sensor_id
            if active is None or active not in self._sensor_facility_by_id:
                self._active_critical_sensor_id = ordered_sensor_ids[0]
            self._last_value_by_sensor = {
                sensor_id: value for sensor_id, value in self._last_value_by_sensor.items() if sensor_id in self._sensor_facility_by_id
            }
            if self._pending_rotate_facility_id is not None:
                self._rotate_active_sensor_locked(prefer_not_facility_id=self._pending_rotate_facility_id)
                self._pending_rotate_facility_id = None

    def mark_incident_resolved(self, *, facility_id: int | None = None) -> int | None:
        with self._lock:
            if facility_id is not None and self._active_critical_sensor_id is not None:
                active_facility_id = self._sensor_facility_by_id.get(self._active_critical_sensor_id)
                if active_facility_id is not None and int(active_facility_id) != int(facility_id):
                    return self._active_critical_sensor_id
            if facility_id is not None:
                target_facility_id = int(facility_id)
                for sensor_id, sensor_facility_id in self._sensor_facility_by_id.items():
                    if sensor_facility_id == target_facility_id:
                        sensor_type = self._sensor_type_by_id.get(sensor_id, "")
                        self._last_value_by_sensor[sensor_id] = self._normal_target(sensor_type)
            self._pending_rotate_facility_id = int(facility_id) if facility_id is not None else None
            if self._sensor_cycle:
                self._rotate_active_sensor_locked(prefer_not_facility_id=self._pending_rotate_facility_id)
                self._pending_rotate_facility_id = None
            return self._active_critical_sensor_id

    def _rotate_active_sensor_locked(self, *, prefer_not_facility_id: int | None = None) -> None:
        if not self._sensor_cycle:
            self._active_critical_sensor_id = None
            return
        current = self._active_critical_sensor_id
        start_index = self._sensor_cycle.index(current) if current in self._sensor_cycle else -1
        total = len(self._sensor_cycle)
        next_id: int | None = None

        if prefer_not_facility_id is not None:
            for offset in range(1, total + 1):
                candidate = self._sensor_cycle[(start_index + offset) % total]
                candidate_facility = self._sensor_facility_by_id.get(candidate)
                if candidate_facility != prefer_not_facility_id:
                    next_id = candidate
                    break

        if next_id is None:
            if total == 1:
                next_id = self._sensor_cycle[0]
            else:
                next_id = self._sensor_cycle[(start_index + 1) % total]

        self._active_critical_sensor_id = next_id
        if next_id is not None:
            self._last_value_by_sensor.pop(next_id, None)

    @staticmethod
    def _normal_target(sensor_type: str) -> float:
        kind = (sensor_type or "").strip().lower()
        if kind == "temperature":
            return 22.0
        if kind == "humidity":
            return 50.0
        if kind == "voltage":
            return 220.0
        if kind == "pressure":
            return 2.2
        return 50.0

    def _critical_target(self, sensor_type: str, *, sensor_key_str: str) -> float:
        kind = (sensor_type or "").strip().lower()
        if kind == "temperature":
            return 41.0
        if kind == "humidity":
            return 85.0
        if kind == "voltage":
            side = self._voltage_fault_side(sensor_key_str)
            return 260.0 if side > 0 else 175.0
        if kind == "pressure":
            return 3.6
        return 90.0

    @staticmethod
    def _safe_bounds(sensor_type: str) -> tuple[float, float]:
        kind = (sensor_type or "").strip().lower()
        if kind == "temperature":
            return -30.0, 80.0
        if kind == "humidity":
            return 0.0, 100.0
        if kind == "voltage":
            return 100.0, 300.0
        if kind == "pressure":
            return 0.5, 6.0
        return 0.0, 100.0

    @staticmethod
    def _normal_noise(sensor_type: str) -> float:
        kind = (sensor_type or "").strip().lower()
        if kind == "temperature":
            return random.uniform(-0.25, 0.25)
        if kind == "humidity":
            return random.uniform(-0.7, 0.7)
        if kind == "voltage":
            return random.uniform(-0.8, 0.8)
        if kind == "pressure":
            return random.uniform(-0.03, 0.03)
        return random.uniform(-0.6, 0.6)

    @staticmethod
    def _critical_noise(sensor_type: str) -> float:
        kind = (sensor_type or "").strip().lower()
        if kind == "temperature":
            return random.uniform(-0.5, 0.5)
        if kind == "humidity":
            return random.uniform(-1.3, 1.3)
        if kind == "voltage":
            return random.uniform(-2.0, 2.0)
        if kind == "pressure":
            return random.uniform(-0.06, 0.06)
        return random.uniform(-1.0, 1.0)

    @staticmethod
    def _critical_pull_factor(state: SensorDegradationState) -> float:
        k = max(0, min(100, state.level)) / 100.0
        return 0.75 + (0.20 * k)

    @staticmethod
    def _normal_pull_factor() -> float:
        return 0.35

    def _apply_single_critical_mode(self, sensor_type: str, value: float, *, sensor_id: int) -> float:
        with self._lock:
            if not self._sensor_cycle:
                self._sensor_cycle = [sensor_id]
            if self._active_critical_sensor_id is None:
                self._active_critical_sensor_id = self._sensor_cycle[0]
            active_id = self._active_critical_sensor_id
            has_previous = sensor_id in self._last_value_by_sensor
            previous = self._last_value_by_sensor.get(sensor_id, value)

        sensor_key_str = str(sensor_id)
        low, high = self._safe_bounds(sensor_type)
        is_active_critical = sensor_id == active_id
        if not has_previous:
            previous = self._normal_target(sensor_type)

        if is_active_critical:
            target = self._critical_target(sensor_type, sensor_key_str=sensor_key_str)
            noise = self._critical_noise(sensor_type)
            pull = self._critical_pull_factor(self._state)
        else:
            target = self._normal_target(sensor_type)
            noise = self._normal_noise(sensor_type)
            pull = self._normal_pull_factor()

        next_value = previous + (target - previous) * pull + noise
        next_value = self._clamp(next_value, low, high)

        with self._lock:
            self._last_value_by_sensor[sensor_id] = next_value
        return next_value

    def apply(self, sensor_type: str, value: float, *, sensor_key: str | int | None = None) -> float:
        if self._single_critical_mode and sensor_key is not None:
            try:
                sensor_id = int(sensor_key)
            except (TypeError, ValueError):
                sensor_id = None
            if sensor_id is not None:
                return self._apply_single_critical_mode(sensor_type, value, sensor_id=sensor_id)

        state = self._state
        if state.level <= 0:
            return value
        if not state.enabled and not state.recovering and not state.auto_recover:
            return value

        k = state.level / 100.0
        kind = (sensor_type or "").strip().lower()
        is_recovering = state.recovering or (not state.enabled and state.auto_recover and state.level > 0)
        pull_factor = 0.2 + (0.6 * k)
        sensor_key_str = str(sensor_key) if sensor_key is not None else kind

        if kind == "temperature":
            target = 22.0 if is_recovering else 42.0
            noise = self._noise(0.35 + (1.25 * k))
            return self._clamp(value + (target - value) * pull_factor + noise, -30.0, 80.0)
        if kind == "humidity":
            target = 50.0 if is_recovering else 88.0
            noise = self._noise(1.2 + (3.6 * k))
            return self._clamp(value + (target - value) * pull_factor + noise, 0.0, 100.0)
        if kind == "voltage":
            if is_recovering:
                target = 220.0
            else:
                side = self._voltage_fault_side(sensor_key_str)
                target = 265.0 if side > 0 else 170.0
            noise = self._noise(1.5 + (6.0 * k))
            return self._clamp(value + (target - value) * pull_factor + noise, 100.0, 300.0)
        if kind == "pressure":
            target = 2.2 if is_recovering else 3.85
            noise = self._noise(0.04 + (0.22 * k))
            return self._clamp(value + (target - value) * pull_factor + noise, 0.5, 6.0)

        target = 50.0 if is_recovering else 90.0
        noise = self._noise(1.0 + (3.0 * k))
        return value + (target - value) * pull_factor + noise


sensor_degradation_service = SensorDegradationService()
