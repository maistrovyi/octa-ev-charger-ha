"""A real station response: totals missing, per-phase values present, no SoC/temperature.

tests/fixtures/status_phases_only.json is an anonymised /status reply from a two-port
station with a VW e-Golf charging on two phases of port 2.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import STATUS_URL, eid, refresh_with

REAL = json.loads((Path(__file__).parent / "fixtures" / "status_phases_only.json").read_text())


@pytest.fixture
def real() -> dict[str, Any]:
    return copy.deepcopy(REAL)


@pytest.fixture
async def setup_real(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    real: dict[str, Any],
) -> MockConfigEntry:
    aioclient_mock.get(STATUS_URL, json=real)
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


def _state(hass: HomeAssistant, name: str) -> str:
    return hass.states.get(eid("sensor", name)).state


async def test_current_falls_back_to_highest_phase(
    hass: HomeAssistant, setup_real: MockConfigEntry
) -> None:
    # Port 2: current_a is null; L1 15.584 A, L2 15.51 A, L3 0.01 A (two-phase car).
    assert float(_state(hass, "port_2_current")) == pytest.approx(15.584)
    # Port 1 reports a total of 0 A, which is used as is.
    assert float(_state(hass, "port_1_current")) == 0


async def test_voltage_falls_back_to_phase_average(
    hass: HomeAssistant, setup_real: MockConfigEntry
) -> None:
    # voltage_v is null on both ports; phase voltages are present.
    assert float(_state(hass, "port_1_voltage")) == pytest.approx(230.4)  # 233.1/230.0/228.2
    assert float(_state(hass, "port_2_voltage")) == pytest.approx(228.7)  # 227.6/228.0/230.7


async def test_other_values(hass: HomeAssistant, setup_real: MockConfigEntry) -> None:
    assert float(_state(hass, "port_2_power")) == pytest.approx(7.018)
    assert float(_state(hass, "port_2_session_energy")) == pytest.approx(14.2)
    assert float(_state(hass, "port_1_energy_meter")) == pytest.approx(22.389)
    assert _state(hass, "port_1_session_energy") == STATE_UNKNOWN
    assert hass.states.get(eid("switch", "port_2_charging")).state == "on"
    assert hass.states.get(eid("binary_sensor", "port_2_plugged_in")).state == "on"
    assert hass.states.get(eid("binary_sensor", "port_1_plugged_in")).state == "off"


async def test_unreported_readings_have_no_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_real: MockConfigEntry
) -> None:
    """temperature_c and soc_percent are always null here: no 'Unknown' entities."""
    for port in ("1", "2"):
        for name in ("vehicle_battery", "temperature"):
            entity_id = eid("sensor", f"port_{port}_{name}")
            assert entity_registry.async_get(entity_id) is None, entity_id


async def test_reading_gets_entity_once_reported(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    setup_real: MockConfigEntry,
    real: dict[str, Any],
) -> None:
    """A car that does send its battery level gets the sensor on the next poll, no restart."""
    real["ports"]["2"]["soc_percent"]["value"] = 64
    await refresh_with(hass, aioclient_mock, setup_real, json=real)
    assert _state(hass, "port_2_vehicle_battery") == "64.0"
    assert entity_registry.async_get(eid("sensor", "port_1_vehicle_battery")) is None

    # Once created it stays, showing unknown when the car is gone.
    real["ports"]["2"]["soc_percent"]["value"] = None
    await refresh_with(hass, aioclient_mock, setup_real, json=real)
    assert _state(hass, "port_2_vehicle_battery") == STATE_UNKNOWN


async def test_all_phases_missing_is_unknown(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_real: MockConfigEntry,
    real: dict[str, Any],
) -> None:
    port = real["ports"]["2"]
    for key in ("current_l1_a", "current_l2_a", "current_l3_a"):
        port[key]["value"] = None
    for key in ("voltage_l1_v", "voltage_l2_v", "voltage_l3_v"):
        port[key] = None
    await refresh_with(hass, aioclient_mock, setup_real, json=real)
    assert _state(hass, "port_2_current") == STATE_UNKNOWN
    assert _state(hass, "port_2_voltage") == STATE_UNKNOWN
