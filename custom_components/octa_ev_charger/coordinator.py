"""Polling coordinator: one /status request feeds every entity."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EvApiError, EvAuthError, EvStationApi
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_PORTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)

type EvConfigEntry = ConfigEntry[EvCoordinator]


class EvCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches station status on a fixed interval."""

    config_entry: EvConfigEntry

    def __init__(self, hass: HomeAssistant, entry: EvConfigEntry, api: EvStationApi) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_STATION_ID]}",
            update_interval=timedelta(seconds=interval),
        )
        self.api = api
        self.station_id: str = entry.data[CONF_STATION_ID]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_status()
        except EvAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EvApiError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def port_ids(self) -> list[str]:
        """Ports reported by the station, sorted; defaults if none yet."""
        ports = (self.data or {}).get("ports")
        if isinstance(ports, dict) and ports:
            return sorted(ports, key=lambda p: (len(p), p))
        return list(DEFAULT_PORTS)

    def port(self, port_id: str) -> dict[str, Any] | None:
        """Raw data for one port, or None."""
        ports = (self.data or {}).get("ports")
        if isinstance(ports, dict):
            data = ports.get(port_id)
            if isinstance(data, dict):
                return data
        return None
