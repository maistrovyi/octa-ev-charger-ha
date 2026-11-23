"""Charging switch, current-limit slider and start/stop buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import BASE, eid, refresh_with


def _calls(aioclient_mock: AiohttpClientMocker) -> list[tuple[str, str, Any]]:
    return [(c[0], str(c[1]), c[2]) for c in aioclient_mock.mock_calls]


# --- switch -----------------------------------------------------------------


async def test_switch_state_and_icon(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    on = hass.states.get(eid("switch", "port_1_charging"))
    off = hass.states.get(eid("switch", "port_2_charging"))
    assert on.state == STATE_ON
    assert on.attributes["icon"] == "mdi:ev-station"
    assert off.state == STATE_OFF
    assert off.attributes["icon"] == "mdi:power-plug-off-outline"


@pytest.mark.parametrize(
    ("status_value", "icon"),
    [
        ("Preparing", "mdi:ev-plug-type2"),
        ("SuspendedEV", "mdi:ev-plug-type2"),
        ("Faulted", "mdi:alert-circle"),
        ("Available", "mdi:power-plug-off-outline"),
    ],
)
async def test_switch_icon_follows_status(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
    status_value: str,
    icon: str,
) -> None:
    status["ports"]["2"]["status"] = status_value
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    assert hass.states.get(eid("switch", "port_2_charging")).attributes["icon"] == icon


@pytest.mark.parametrize(("service", "path"), [("turn_on", "start"), ("turn_off", "stop")])
async def test_switch_sends_command_and_refreshes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    service: str,
    path: str,
) -> None:
    aioclient_mock.post(f"{BASE}/ports/2/{path}", status=200)
    polls_before = sum(1 for c in aioclient_mock.mock_calls if c[0] == "GET")

    await hass.services.async_call(
        "switch", service, {ATTR_ENTITY_ID: eid("switch", "port_2_charging")}, blocking=True
    )

    assert ("POST", f"{BASE}/ports/2/{path}", None) in _calls(aioclient_mock)
    polls_after = sum(1 for c in aioclient_mock.mock_calls if c[0] == "GET")
    assert polls_after > polls_before, "status re-polled after the command"


async def test_switch_error_is_reported(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, init_integration: MockConfigEntry
) -> None:
    aioclient_mock.post(f"{BASE}/ports/2/start", status=409, text="no car")
    with pytest.raises(HomeAssistantError, match="Port 2: could not start charging") as err:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: eid("switch", "port_2_charging")}, blocking=True
        )
    assert err.value.translation_key == "start_failed"
    assert err.value.translation_placeholders["port"] == "2"


# --- number -----------------------------------------------------------------


async def test_number_value_and_range(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    p1 = hass.states.get(eid("number", "port_1_current_limit"))
    p2 = hass.states.get(eid("number", "port_2_current_limit"))
    assert p1.state == "32.0"  # no saved limit -> port max
    assert (p1.attributes["min"], p1.attributes["max"]) == (6, 32)
    assert p2.state == "10.0"
    assert p2.attributes["max"] == 16  # per-port max from the API


async def test_number_set_value(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, init_integration: MockConfigEntry
) -> None:
    aioclient_mock.put(f"{BASE}/ports/2/current_limit", status=200)
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: eid("number", "port_2_current_limit"), "value": 12},
        blocking=True,
    )
    assert ("PUT", f"{BASE}/ports/2/current_limit", {"current_limit_a": 12}) in _calls(
        aioclient_mock
    )


async def test_number_rejects_out_of_range(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    with pytest.raises(Exception):  # ServiceValidationError subclass in current HA
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: eid("number", "port_2_current_limit"), "value": 20},
            blocking=True,
        )


async def test_number_error_is_reported(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, init_integration: MockConfigEntry
) -> None:
    aioclient_mock.put(f"{BASE}/ports/1/current_limit", status=500)
    with pytest.raises(HomeAssistantError, match="Port 1: could not set current limit"):
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: eid("number", "port_1_current_limit"), "value": 16},
            blocking=True,
        )


async def test_number_unknown_without_values(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    init_integration: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    status["ports"]["1"]["current_max_a"] = None
    await refresh_with(hass, aioclient_mock, init_integration, json=status)
    st = hass.states.get(eid("number", "port_1_current_limit"))
    assert st.state == "unknown"
    assert st.attributes["max"] == 32  # falls back to the default maximum


# --- buttons (disabled by default) ------------------------------------------


async def test_buttons_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, init_integration: MockConfigEntry
) -> None:
    entry = entity_registry.async_get(eid("button", "port_1_start"))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("action", ["start", "stop"])
async def test_button_press(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    action: str,
) -> None:
    button = eid("button", f"port_1_{action}")
    entity_registry.async_update_entity(button, disabled_by=None)
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.post(f"{BASE}/ports/1/{action}", status=200)
    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: button}, blocking=True)
    assert ("POST", f"{BASE}/ports/1/{action}", None) in _calls(aioclient_mock)

    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{BASE}/ports/1/{action}", status=500)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: button}, blocking=True)
