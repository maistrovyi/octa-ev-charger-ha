"""HTTP client: auth header, URLs and error mapping."""

from __future__ import annotations

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.octa_ev_charger.api import EvApiError, EvAuthError, EvStationApi

from .conftest import BASE, HOST, STATION, STATUS_URL


def _api(hass: HomeAssistant, token: str = "abc", host: str = HOST) -> EvStationApi:
    return EvStationApi(async_get_clientsession(hass), host, STATION, token)


@pytest.mark.parametrize(
    ("token", "header"),
    [
        ("abc", "Bearer abc"),
        ("Bearer abc", "Bearer abc"),
        ("  bearer abc ", "bearer abc"),
    ],
)
async def test_bearer_prefix(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, token: str, header: str
) -> None:
    aioclient_mock.get(STATUS_URL, json={"online": True})
    await _api(hass, token).get_status()
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == header


async def test_trailing_slash_in_host(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(STATUS_URL, json={"online": True})
    assert await _api(hass, host=f"{HOST}/").get_status() == {"online": True}


async def test_commands(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(f"{BASE}/ports/1/start", status=200)
    aioclient_mock.post(f"{BASE}/ports/1/stop", status=202)
    aioclient_mock.put(f"{BASE}/ports/1/current_limit", status=200)
    api = _api(hass)

    assert await api.start("1") == 200
    assert await api.stop("1") == 202
    assert await api.set_current_limit("1", 12.7) == 200
    assert aioclient_mock.mock_calls[-1][2] == {"current_limit_a": 12}


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    aioclient_mock.get(STATUS_URL, status=status)
    with pytest.raises(EvAuthError):
        await _api(hass).get_status()


async def test_server_error(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(STATUS_URL, status=500, text="boom")
    with pytest.raises(EvApiError, match="HTTP 500 boom"):
        await _api(hass).get_status()


@pytest.mark.parametrize("exc", [aiohttp.ClientError(), TimeoutError()])
async def test_network_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, exc: Exception
) -> None:
    aioclient_mock.get(STATUS_URL, exc=exc)
    with pytest.raises(EvApiError):
        await _api(hass).get_status()


async def test_invalid_json(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(STATUS_URL, text="<html>not json</html>")
    with pytest.raises(EvApiError, match="Invalid JSON"):
        await _api(hass).get_status()


async def test_non_object_json(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(STATUS_URL, json=[1, 2, 3])
    with pytest.raises(EvApiError, match="Unexpected"):
        await _api(hass).get_status()
