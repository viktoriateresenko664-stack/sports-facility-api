from __future__ import annotations

import asyncio
import logging

from scripts.generate_fake_sensor_data import generate_fake_sensor_data_once
from app.services.sensor_degradation_service import sensor_degradation_service

logger = logging.getLogger(__name__)


class SensorDataAutoGenService:
    def __init__(self, interval_seconds: int = 300) -> None:
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="sensor-data-autogen")
        logger.info("Sensor auto generation started (interval=%ss)", self.interval_seconds)

    async def stop(self) -> None:
        if not self.is_running:
            return
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Sensor auto generation stopped")

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                sensor_degradation_service.tick()
                created = await asyncio.to_thread(generate_fake_sensor_data_once)
                state = sensor_degradation_service.get_state()
                logger.info(
                    "Sensor auto generation tick: created=%s degradation_enabled=%s degradation_level=%s",
                    created,
                    state.enabled,
                    state.level,
                )
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Sensor auto generation loop failed")
        finally:
            self._task = None


sensor_data_autogen_service = SensorDataAutoGenService(interval_seconds=300)
