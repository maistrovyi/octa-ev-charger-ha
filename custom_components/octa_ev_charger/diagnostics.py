"""Diagnostics download (Settings → Devices → … → Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_SCAN_INTERVAL, CONF_STATION_ID, CONF_TOKEN, DEFAULT_SCAN_INTERVAL
from .coordinator import EvConfigEntry

TO_REDACT = {CONF_HOST, CONF_STATION_ID, CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EvConfigEntry
) -> dict[str, Any]:
    """Config (host, station and token redacted), options and the last raw status payload."""
    coordinator = entry.runtime_data
    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "scan_interval": entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        "last_update_success": coordinator.last_update_success,
        "ports": coordinator.port_ids,
        "status": coordinator.data,
    }
