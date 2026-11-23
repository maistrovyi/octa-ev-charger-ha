"""Base entity: every entity belongs to the one station device."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, PLUGGED_IN_STATUSES, PROBLEM_STATUSES
from .coordinator import EvConfigEntry, EvCoordinator


def num(raw: Any) -> float | None:
    """Accept 12.3, "12.3" or {"value": 12.3}; anything else -> None."""
    if isinstance(raw, dict):
        raw = raw.get("value")
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def status_of(port: dict[str, Any] | None) -> str | None:
    """Port status lower-cased, or None."""
    if port and isinstance(port.get("status"), str):
        return port["status"].lower()
    return None


def is_plugged_in(port: dict[str, Any] | None) -> bool | None:
    status = status_of(port)
    return None if status is None else status in PLUGGED_IN_STATUSES


def has_problem(port: dict[str, Any] | None) -> bool | None:
    status = status_of(port)
    return None if status is None else status in PROBLEM_STATUSES


def async_add_port_entities(
    entry: EvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[str], Iterable[Entity]],
) -> None:
    """Add a port's entities when the station first reports that port.

    Runs at setup and after every poll, so a station that was offline at startup,
    or that gains a port later, gets its entities without a restart. Ports that
    disappear keep their entities, which then show as unavailable.
    """
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_ports() -> None:
        new = [port for port in coordinator.port_ids if port not in known]
        if not new:
            return
        LOGGER.debug("Station %s: adding port(s) %s", coordinator.station_id, ", ".join(new))
        known.update(new)
        async_add_entities([entity for port in new for entity in factory(port)])

    _add_new_ports()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_ports))


class EvEntity(CoordinatorEntity[EvCoordinator]):
    """Station-level entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EvCoordinator, key: str) -> None:
        super().__init__(coordinator)
        station = coordinator.station_id
        self._attr_unique_id = f"{station}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station)},
            name=f"EV Station {station}",
            manufacturer="Octa",
            model="EV charging station",
            configuration_url=coordinator.config_entry.data.get("host"),
        )


class EvPortEntity(EvEntity):
    """Entity bound to one port of the station."""

    def __init__(self, coordinator: EvCoordinator, port_id: str, key: str) -> None:
        super().__init__(coordinator, f"p{port_id}_{key}")
        self.port_id = port_id
        # Names come from translations/<lang>.json, e.g. "Port {port} power".
        self._attr_translation_placeholders = {"port": port_id}

    def command_error(self, translation_key: str, err: Exception) -> HomeAssistantError:
        """Translated error for a failed command on this port."""
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"port": self.port_id, "error": str(err)},
        )

    @property
    def port_data(self) -> dict[str, Any] | None:
        return self.coordinator.port(self.port_id)

    @property
    def available(self) -> bool:
        return super().available and self.port_data is not None
