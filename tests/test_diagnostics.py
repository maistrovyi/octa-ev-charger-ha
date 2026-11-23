"""Diagnostics must not leak the token, server or station ID."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import HOST, STATION, TOKEN


async def test_diagnostics_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["config"] == {
        "host": "**REDACTED**",
        "station_id": "**REDACTED**",
        "token": "**REDACTED**",
    }
    assert diag["scan_interval"] == 30
    assert diag["last_update_success"] is True
    assert diag["ports"] == ["1", "2"]
    assert diag["status"]["ports"]["1"]["status"] == "Charging"

    dumped = json.dumps(diag)
    for secret in (TOKEN, HOST, STATION):
        assert secret not in dumped
