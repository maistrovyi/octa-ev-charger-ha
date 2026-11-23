"""Current limit slider per port."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import EvApiError
from .const import DEFAULT_MAX_CURRENT_A, MIN_CURRENT_A
from .coordinator import EvConfigEntry, EvCoordinator
from .entity import EvPortEntity, async_add_port_entities, num


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_port_entities(
        entry, async_add_entities, lambda port: [EvCurrentLimit(coordinator, port)]
    )


class EvCurrentLimit(EvPortEntity, NumberEntity):
    """Saved current limit. Shows the port maximum when no limit is saved."""

    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = MIN_CURRENT_A
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EvCoordinator, port_id: str) -> None:
        super().__init__(coordinator, port_id, "current_limit_number")
        self._attr_translation_key = "current_limit"

    @property
    def native_max_value(self) -> float:
        port = self.port_data or {}
        return num(port.get("current_max_a")) or DEFAULT_MAX_CURRENT_A

    @property
    def native_value(self) -> float | None:
        port = self.port_data
        if port is None:
            return None
        return num(port.get("current_limit_a")) or num(port.get("current_max_a"))

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.api.set_current_limit(self.port_id, int(value))
        except EvApiError as err:
            raise self.command_error("set_current_failed", err) from err
        await self.coordinator.async_request_refresh()
