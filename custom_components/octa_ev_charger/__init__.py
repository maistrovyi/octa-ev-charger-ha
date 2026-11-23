"""Octa EV Charger: one device per station with all station and port entities."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EvStationApi
from .const import CONF_STATION_ID, CONF_TOKEN
from .coordinator import EvConfigEntry, EvCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: EvConfigEntry) -> bool:
    api = EvStationApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_STATION_ID],
        entry.data[CONF_TOKEN],
    )
    coordinator = EvCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EvConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
