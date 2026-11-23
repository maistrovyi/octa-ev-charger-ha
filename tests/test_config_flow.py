"""UI setup, re-authentication and options."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.octa_ev_charger.const import CONF_SCAN_INTERVAL, DOMAIN

from .conftest import ENTRY_DATA, HOST, STATION, STATUS_URL

USER_INPUT = {"host": "ev.example.com/", "station_id": f" {STATION} ", "token": " test-token "}


@pytest.fixture
def mock_setup_entry():
    with patch("custom_components.octa_ev_charger.async_setup_entry", return_value=True) as mock:
        yield mock


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_setup_entry
) -> None:
    aioclient_mock.get(STATUS_URL, json={"online": True})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EV Station {STATION}"
    # Host gets a scheme and loses the trailing slash; values are trimmed.
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == f"{HOST}|{STATION}"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("response", "error"),
    [({"status": 401}, "invalid_auth"), ({"status": 500}, "cannot_connect")],
)
async def test_user_flow_errors_then_recover(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
    response: dict,
    error: str,
) -> None:
    aioclient_mock.get(STATUS_URL, **response)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS_URL, json={"online": True})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    mock_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    mock_setup_entry,
) -> None:
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.get(STATUS_URL, status=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"token": "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS_URL, json={"online": True})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"token": "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data["token"] == "new-token"


async def test_options_flow_reloads(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, init_integration
) -> None:
    entry = init_integration
    assert entry.runtime_data.update_interval.total_seconds() == 30

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 15}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 15}
    # Reloaded with a new coordinator using the new interval.
    assert entry.runtime_data.update_interval.total_seconds() == 15
