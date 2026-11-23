"""Online, charging, plugged-in and problem sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import eid, refresh_with


async def test_initial_states(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    expected = {
        "online": STATE_ON,
        "port_1_charging": STATE_ON,
        "port_1_plugged_in": STATE_ON,
        "port_1_problem": STATE_OFF,
        "port_2_charging": STATE_OFF,
        "port_2_plugged_in": STATE_OFF,
        "port_2_problem": STATE_OFF,
    }
    for name, state in expected.items():
        assert hass.states.get(eid("binary_sensor", name)).state == state, name


@pytest.mark.parametrize(
    ("status_value", "plugged_in", "problem"),
    [
        ("Available", STATE_OFF, STATE_OFF),
        ("Preparing", STATE_ON, STATE_OFF),
        ("Charging", STATE_ON, STATE_OFF),
        ("SuspendedEV", STATE_ON, STATE_OFF),
        ("SuspendedEVSE", STATE_ON, STATE_OFF),
        ("Finishing", STATE_ON, STATE_OFF),
        ("charging", STATE_ON, STATE_OFF),  # case-insensitive
        ("Faulted", STATE_OFF, STATE_ON),
        ("Unavailable", STATE_OFF, STATE_ON),
        (None, STATE_UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_status_mapping(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
    status_value: str | None,
    plugged_in: str,
    problem: str,
) -> None:
    status["ports"]["2"]["status"] = status_value
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    assert hass.states.get(eid("binary_sensor", "port_2_plugged_in")).state == plugged_in
    assert hass.states.get(eid("binary_sensor", "port_2_problem")).state == problem


async def test_charging_non_bool_is_unknown(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    status["ports"]["1"]["charging"] = "yes"
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    assert hass.states.get(eid("binary_sensor", "port_1_charging")).state == STATE_UNKNOWN


async def test_online_off_not_unavailable_when_api_down(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, init_integration: MockConfigEntry
) -> None:
    await refresh_with(hass, aioclient_mock, init_integration, status=503)
    assert hass.states.get(eid("binary_sensor", "online")).state == STATE_OFF


async def test_online_follows_payload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    status["online"] = False
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    assert hass.states.get(eid("binary_sensor", "online")).state == STATE_OFF
