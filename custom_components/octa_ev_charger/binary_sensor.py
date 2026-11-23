"""Binary sensors for the EV station."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EvConfigEntry, EvCoordinator
from .entity import EvEntity, EvPortEntity, async_add_port_entities, has_problem, is_plugged_in


def _charging(port: dict[str, Any]) -> bool | None:
    value = port.get("charging")
    return value if isinstance(value, bool) else None


@dataclass(frozen=True, kw_only=True)
class EvPortBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


PORT_BINARY_SENSORS: tuple[EvPortBinaryDescription, ...] = (
    EvPortBinaryDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_charging,
    ),
    EvPortBinaryDescription(
        key="plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=is_plugged_in,
    ),
    EvPortBinaryDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=has_problem,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([EvOnlineSensor(coordinator)])
    async_add_port_entities(
        entry,
        async_add_entities,
        lambda port: [EvPortBinarySensor(coordinator, port, d) for d in PORT_BINARY_SENSORS],
    )


class EvOnlineSensor(EvEntity, BinarySensorEntity):
    """Station connected to the server. Off (not unavailable) if the API is unreachable."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EvCoordinator) -> None:
        super().__init__(coordinator, "online")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get("online"))


class EvPortBinarySensor(EvPortEntity, BinarySensorEntity):
    entity_description: EvPortBinaryDescription

    def __init__(
        self, coordinator: EvCoordinator, port_id: str, desc: EvPortBinaryDescription
    ) -> None:
        super().__init__(coordinator, port_id, desc.key)
        self.entity_description = desc
        self._attr_translation_key = desc.key

    @property
    def is_on(self) -> bool | None:
        port = self.port_data
        return None if port is None else self.entity_description.value_fn(port)
