"""Stations with 1, 2 or 3 ports, and ports that appear or disappear at runtime."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import STATUS_URL, eid, refresh_with

# Entities each port gets: 3 binary sensors, 18 sensors, switch, number, 2 buttons.
PER_PORT = 3 + 18 + 1 + 1 + 2
# Station-level: online + total power.
STATION = 2


def _with_ports(status: dict[str, Any], port_ids: list[str]) -> dict[str, Any]:
    """Payload whose ports are copies of the sample port 1 (charging at 7.2 kW)."""
    template = status["ports"]["1"]
    return {**status, "ports": {p: copy.deepcopy(template) for p in port_ids}}


async def _setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
    payload: dict[str, Any],
) -> None:
    aioclient_mock.get(STATUS_URL, json=payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _port_numbers(entity_registry: er.EntityRegistry, entry: MockConfigEntry) -> set[str]:
    return {
        e.unique_id.split("_")[1][1:]  # "<station>_p3_power" -> "3"
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if e.unique_id.split("_")[1].startswith("p")
    }


@pytest.mark.parametrize("ports", [["1"], ["1", "2"], ["1", "2", "3"]])
async def test_entities_per_port_count(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
    ports: list[str],
) -> None:
    await _setup(hass, aioclient_mock, mock_entry, _with_ports(status, ports))

    entities = er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id)
    assert len(entities) == STATION + PER_PORT * len(ports)
    assert _port_numbers(entity_registry, mock_entry) == set(ports)
    # Total power sums every port (7.2 kW each in this payload).
    total = float(hass.states.get(eid("sensor", "total_power")).state)
    assert total == pytest.approx(7.2 * len(ports))


async def test_three_ports_named_and_controllable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    await _setup(hass, aioclient_mock, mock_entry, _with_ports(status, ["1", "2", "3"]))
    state = hass.states.get(eid("switch", "port_3_charging"))
    assert state.state == "on"
    assert state.attributes["friendly_name"].endswith("Port 3 charging")
    assert hass.states.get(eid("number", "port_3_current_limit")) is not None


async def test_offline_at_startup_then_ports_appear(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    """No guessing: port entities appear once the station reports its ports."""
    await _setup(hass, aioclient_mock, mock_entry, {"online": False})
    assert _port_numbers(entity_registry, mock_entry) == set()
    assert hass.states.get(eid("binary_sensor", "online")).state == "off"

    await refresh_with(hass, aioclient_mock, mock_entry, json=_with_ports(status, ["1", "2", "3"]))

    assert _port_numbers(entity_registry, mock_entry) == {"1", "2", "3"}
    assert hass.states.get(eid("sensor", "port_3_power")).state == "7.2"
    devices = dr.async_entries_for_config_entry(device_registry, mock_entry.entry_id)
    assert len(devices) == 1, "new ports join the existing station device"


async def test_port_added_later(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    await _setup(hass, aioclient_mock, mock_entry, _with_ports(status, ["1", "2"]))
    assert hass.states.get(eid("switch", "port_3_charging")) is None

    await refresh_with(hass, aioclient_mock, mock_entry, json=_with_ports(status, ["1", "2", "3"]))
    assert hass.states.get(eid("switch", "port_3_charging")).state == "on"

    # Polling again with the same ports adds nothing twice.
    before = len(er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id))
    await refresh_with(hass, aioclient_mock, mock_entry, json=_with_ports(status, ["1", "2", "3"]))
    after = len(er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id))
    assert after == before == STATION + 3 * PER_PORT


async def test_port_removed_keeps_entities_unavailable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    await _setup(hass, aioclient_mock, mock_entry, _with_ports(status, ["1", "2", "3"]))
    await refresh_with(hass, aioclient_mock, mock_entry, json=_with_ports(status, ["1", "2"]))

    assert hass.states.get(eid("switch", "port_3_charging")).state == STATE_UNAVAILABLE
    assert _port_numbers(entity_registry, mock_entry) == {"1", "2", "3"}
    assert float(hass.states.get(eid("sensor", "total_power")).state) == pytest.approx(14.4)


async def test_port_order_is_numeric(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    await _setup(hass, aioclient_mock, mock_entry, _with_ports(status, ["10", "2", "1"]))
    assert mock_entry.runtime_data.port_ids == ["1", "2", "10"]


async def test_unloading_stops_watching_for_ports(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    await _setup(hass, aioclient_mock, mock_entry, _with_ports(status, ["1"]))
    coordinator = mock_entry.runtime_data
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert not coordinator._listeners
