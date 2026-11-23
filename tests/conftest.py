"""Shared fixtures: a fake station API and a loaded config entry."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.octa_ev_charger.const import DOMAIN

HOST = "https://ev.example.com"
STATION = "station-1"
TOKEN = "test-token"
BASE = f"{HOST}/api/home-assistant/v1/stations/{STATION}"
STATUS_URL = f"{BASE}/status"
ENTRY_DATA = {"host": HOST, "station_id": STATION, "token": TOKEN}

# Entity IDs derive from the device name "EV Station station-1".
PREFIX = "ev_station_station_1"

_STATUS = json.loads((Path(__file__).parent / "fixtures" / "status.json").read_text())


def eid(platform: str, name: str) -> str:
    """Entity ID for a name like 'port_1_power'."""
    return f"{platform}.{PREFIX}_{name}"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load integrations from custom_components/."""


@pytest.fixture(autouse=True)
def no_command_delay():
    """Skip the post-command wait so tests run instantly."""
    with (
        patch("custom_components.octa_ev_charger.switch.COMMAND_REFRESH_DELAY", 0),
        patch("custom_components.octa_ev_charger.button.COMMAND_REFRESH_DELAY", 0),
    ):
        yield


@pytest.fixture
def status() -> dict[str, Any]:
    """A fresh copy of the sample status payload."""
    return copy.deepcopy(_STATUS)


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{HOST}|{STATION}",
        title=f"EV Station {STATION}",
        data=dict(ENTRY_DATA),
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> MockConfigEntry:
    """Set up the integration against the sample payload."""
    aioclient_mock.get(STATUS_URL, json=status)
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


async def refresh_with(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
    **response: Any,
) -> None:
    """Make the next poll return `response` and run it."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS_URL, **response)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
