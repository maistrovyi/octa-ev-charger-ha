"""Sensors for the EV station."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EvConfigEntry, EvCoordinator
from .entity import EvEntity, EvPortEntity, num


@dataclass(frozen=True, kw_only=True)
class EvPortSensorDescription(SensorEntityDescription):
    """Port sensor: how to read its value from the port's JSON."""

    value_fn: Callable[[dict[str, Any]], Any]


def _field(key: str) -> Callable[[dict[str, Any]], float | None]:
    return lambda port: num(port.get(key))


def _text(key: str) -> Callable[[dict[str, Any]], str | None]:
    return lambda port: port[key] if isinstance(port.get(key), str) else None


def _limit(port: dict[str, Any]) -> float | None:
    """Saved limit, or the port maximum when no limit is saved."""
    return num(port.get("current_limit_a")) or num(port.get("current_max_a"))


_CURRENT = {
    "device_class": SensorDeviceClass.CURRENT,
    "native_unit_of_measurement": UnitOfElectricCurrent.AMPERE,
    "state_class": SensorStateClass.MEASUREMENT,
}
_VOLTAGE = {
    "device_class": SensorDeviceClass.VOLTAGE,
    "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
    "state_class": SensorStateClass.MEASUREMENT,
}

PORT_SENSORS: tuple[EvPortSensorDescription, ...] = (
    EvPortSensorDescription(key="status", icon="mdi:ev-station", value_fn=_text("status")),
    EvPortSensorDescription(
        key="scenario",
        icon="mdi:script-text-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("scenario"),
    ),
    EvPortSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_field("power_kw"),
    ),
    EvPortSensorDescription(key="current", value_fn=_field("current_a"), **_CURRENT),
    EvPortSensorDescription(
        key="current_l1",
        value_fn=_field("current_l1_a"),
        entity_registry_enabled_default=False,
        **_CURRENT,
    ),
    EvPortSensorDescription(
        key="current_l2",
        value_fn=_field("current_l2_a"),
        entity_registry_enabled_default=False,
        **_CURRENT,
    ),
    EvPortSensorDescription(
        key="current_l3",
        value_fn=_field("current_l3_a"),
        entity_registry_enabled_default=False,
        **_CURRENT,
    ),
    EvPortSensorDescription(
        key="current_offered",
        value_fn=_field("current_offered_a"),
        **_CURRENT,
    ),
    EvPortSensorDescription(
        key="current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_limit,
    ),
    EvPortSensorDescription(
        key="current_max",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("current_max_a"),
    ),
    EvPortSensorDescription(key="voltage", value_fn=_field("voltage_v"), **_VOLTAGE),
    EvPortSensorDescription(
        key="voltage_l1",
        value_fn=_field("voltage_l1_v"),
        entity_registry_enabled_default=False,
        **_VOLTAGE,
    ),
    EvPortSensorDescription(
        key="voltage_l2",
        value_fn=_field("voltage_l2_v"),
        entity_registry_enabled_default=False,
        **_VOLTAGE,
    ),
    EvPortSensorDescription(
        key="voltage_l3",
        value_fn=_field("voltage_l3_v"),
        entity_registry_enabled_default=False,
        **_VOLTAGE,
    ),
    EvPortSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("temperature_c"),
    ),
    EvPortSensorDescription(
        key="soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_field("soc_percent"),
    ),
    EvPortSensorDescription(
        key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field("session_energy_kwh"),
    ),
    EvPortSensorDescription(
        key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field("energy_total_kwh"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [EvTotalPowerSensor(coordinator)]
    for port_id in coordinator.port_ids:
        entities.extend(EvPortSensor(coordinator, port_id, desc) for desc in PORT_SENSORS)
    async_add_entities(entities)


class EvPortSensor(EvPortEntity, SensorEntity):
    """A value read from one port."""

    entity_description: EvPortSensorDescription

    def __init__(
        self, coordinator: EvCoordinator, port_id: str, desc: EvPortSensorDescription
    ) -> None:
        super().__init__(coordinator, port_id, desc.key)
        self.entity_description = desc
        self._attr_translation_key = desc.key

    @property
    def native_value(self) -> Any:
        port = self.port_data
        return None if port is None else self.entity_description.value_fn(port)


class EvTotalPowerSensor(EvEntity, SensorEntity):
    """Sum of all ports' power."""

    _attr_translation_key = "total_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EvCoordinator) -> None:
        super().__init__(coordinator, "total_power")

    @property
    def native_value(self) -> float | None:
        values = [
            num(port.get("power_kw"))
            for pid in self.coordinator.port_ids
            if (port := self.coordinator.port(pid)) is not None
        ]
        values = [v for v in values if v is not None]
        return round(sum(values), 3) if values else None
