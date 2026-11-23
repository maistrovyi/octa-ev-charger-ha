"""Setup, unload, error states and the single device."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.octa_ev_charger.const import DOMAIN

from .conftest import STATION, STATUS_URL


async def test_setup_and_unload(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_all_entities_on_one_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    entities = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    # 1 online + 1 total power + per port: 3 binary, 18 sensors, switch, number, 2 buttons
    assert len(entities) == 2 + 2 * (3 + 18 + 1 + 1 + 2)
    assert {e.device_id for e in entities} == {entities[0].device_id}

    devices = dr.async_entries_for_config_entry(device_registry, init_integration.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert (DOMAIN, STATION) in device.identifiers
    assert device.name == f"EV Station {STATION}"
    assert device.manufacturer == "Octa"


async def test_setup_retry_when_unreachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(STATUS_URL, status=502)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_token_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(STATUS_URL, status=401)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]
