"""Sensor values, units and defaults."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.octa_ev_charger.entity import num

from .conftest import eid, refresh_with


@pytest.mark.parametrize(
    ("name", "state", "unit"),
    [
        ("port_1_status", "Charging", None),
        ("port_1_scenario", "manual", None),
        ("port_1_power", "7.2", "kW"),
        ("port_1_current", "31.5", "A"),
        ("port_1_current_offered", "32.0", "A"),
        ("port_1_active_current_limit", "32.0", "A"),  # no saved limit -> port max
        ("port_2_active_current_limit", "10.0", "A"),  # saved limit wins
        ("port_1_max_current", "32.0", "A"),
        ("port_1_voltage", "230.1", "V"),
        ("port_1_temperature", "41.0", "°C"),
        ("port_1_vehicle_battery", "55.0", "%"),
        ("port_1_session_energy", "3.4", "kWh"),
        ("port_1_energy_meter", "1234.5", "kWh"),
        ("port_2_energy_meter", "88.0", "kWh"),
        ("total_power", "7.2", "kW"),
        # nulls in the payload become "unknown", never 0
        ("port_2_voltage", STATE_UNKNOWN, "V"),
        ("port_2_session_energy", STATE_UNKNOWN, "kWh"),
        ("port_2_scenario", STATE_UNKNOWN, None),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant, init_integration: MockConfigEntry, name: str, state: str, unit: str | None
) -> None:
    st = hass.states.get(eid("sensor", name))
    assert st is not None, name
    assert st.state == state
    assert st.attributes.get("unit_of_measurement") == unit


async def test_energy_meter_is_total_increasing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    attrs = hass.states.get(eid("sensor", "port_1_energy_meter")).attributes
    assert attrs["state_class"] == "total_increasing"
    assert attrs["device_class"] == "energy"


async def test_per_phase_sensors_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, init_integration: MockConfigEntry
) -> None:
    for name in ("port_1_current_l1", "port_1_voltage_l3", "port_2_current_l2"):
        entry = entity_registry.async_get(eid("sensor", name))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(eid("sensor", name)) is None


async def test_total_power_unknown_when_no_readings(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    for port in status["ports"].values():
        port["power_kw"] = None
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    assert hass.states.get(eid("sensor", "total_power")).state == STATE_UNKNOWN


async def test_unavailable_when_api_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, init_integration: MockConfigEntry
) -> None:
    await refresh_with(hass, aioclient_mock, init_integration, status=500)
    assert hass.states.get(eid("sensor", "port_1_power")).state == STATE_UNAVAILABLE
    assert hass.states.get(eid("sensor", "port_1_energy_meter")).state == STATE_UNAVAILABLE


async def test_port_disappears(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    del status["ports"]["2"]
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    assert hass.states.get(eid("sensor", "port_2_power")).state == STATE_UNAVAILABLE
    assert hass.states.get(eid("sensor", "port_1_power")).state == "7.2"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (5, 5.0),
        (2.5, 2.5),
        ("3.1", 3.1),
        ({"value": 7}, 7.0),
        ({"value": None}, None),
        ({}, None),
        (None, None),
        (True, None),
        ("n/a", None),
        ([1], None),
    ],
)
def test_num(raw: Any, expected: float | None) -> None:
    assert num(raw) == expected
