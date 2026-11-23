"""Charging switch per port: on = start, off = stop."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import EvApiError
from .const import COMMAND_REFRESH_DELAY
from .coordinator import EvConfigEntry, EvCoordinator
from .entity import EvPortEntity, status_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(EvChargingSwitch(coordinator, p) for p in coordinator.port_ids)


class EvChargingSwitch(EvPortEntity, SwitchEntity):
    """Shows whether the port is charging and starts/stops it."""

    def __init__(self, coordinator: EvCoordinator, port_id: str) -> None:
        super().__init__(coordinator, port_id, "charging_switch")
        self._attr_translation_key = "charging"

    @property
    def is_on(self) -> bool | None:
        port = self.port_data
        if port is None or not isinstance(port.get("charging"), bool):
            return None
        return port["charging"]

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:ev-station"
        status = status_of(self.port_data)
        if status in ("faulted", "unavailable"):
            return "mdi:alert-circle"
        if status and status != "available":
            return "mdi:ev-plug-type2"
        return "mdi:power-plug-off-outline"

    async def _command(self, start: bool) -> None:
        api = self.coordinator.api
        try:
            if start:
                await api.start(self.port_id)
            else:
                await api.stop(self.port_id)
        except EvApiError as err:
            raise self.command_error("start_failed" if start else "stop_failed", err) from err
        await asyncio.sleep(COMMAND_REFRESH_DELAY)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._command(False)
