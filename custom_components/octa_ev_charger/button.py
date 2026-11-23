"""Start/stop buttons per port (handy for scripts; the switch does the same)."""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import EvApiError
from .const import COMMAND_REFRESH_DELAY
from .coordinator import EvConfigEntry, EvCoordinator
from .entity import EvPortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        EvCommandButton(coordinator, port_id, start)
        for port_id in coordinator.port_ids
        for start in (True, False)
    )


class EvCommandButton(EvPortEntity, ButtonEntity):
    """Sends start or stop to one port."""

    # Hidden by default: the charging switch covers this. Enable if you want them.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: EvCoordinator, port_id: str, start: bool) -> None:
        action = "start" if start else "stop"
        super().__init__(coordinator, port_id, action)
        self._start = start
        self._attr_translation_key = action
        self._attr_icon = "mdi:play" if start else "mdi:stop"

    async def async_press(self) -> None:
        api = self.coordinator.api
        try:
            if self._start:
                await api.start(self.port_id)
            else:
                await api.stop(self.port_id)
        except EvApiError as err:
            raise self.command_error("start_failed" if self._start else "stop_failed", err) from err
        await asyncio.sleep(COMMAND_REFRESH_DELAY)
        await self.coordinator.async_request_refresh()
