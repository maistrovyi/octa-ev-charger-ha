"""Small async client for the station's Home Assistant API."""

from __future__ import annotations

from typing import Any

import aiohttp

API_PREFIX = "/api/home-assistant/v1/stations"
TIMEOUT = aiohttp.ClientTimeout(total=15)


class EvApiError(Exception):
    """Request failed (network, server error, unexpected response)."""


class EvAuthError(EvApiError):
    """Token rejected (401/403)."""


class EvStationApi:
    """Talks to https://<host>/api/home-assistant/v1/stations/<station>/..."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        station_id: str,
        token: str,
    ) -> None:
        self._session = session
        self._base = f"{host.rstrip('/')}{API_PREFIX}/{station_id}"
        token = token.strip()
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        self._headers = {"Authorization": token}

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> aiohttp.ClientResponse:
        try:
            resp = await self._session.request(
                method,
                f"{self._base}{path}",
                headers=self._headers,
                json=json,
                timeout=TIMEOUT,
            )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise EvApiError(f"{method} {path}: {err}") from err
        if resp.status in (401, 403):
            raise EvAuthError(f"{method} {path}: HTTP {resp.status}")
        if resp.status >= 400:
            body = await resp.text()
            raise EvApiError(f"{method} {path}: HTTP {resp.status} {body[:200]}")
        return resp

    async def get_status(self) -> dict[str, Any]:
        """Return the station status JSON."""
        resp = await self._request("GET", "/status")
        try:
            data = await resp.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise EvApiError(f"Invalid JSON from /status: {err}") from err
        if not isinstance(data, dict):
            raise EvApiError("Unexpected /status payload")
        return data

    async def start(self, port: str) -> int:
        """Start charging. Returns HTTP status (200 accepted, 202 pending)."""
        return (await self._request("POST", f"/ports/{port}/start")).status

    async def stop(self, port: str) -> int:
        """Stop charging. Returns HTTP status."""
        return (await self._request("POST", f"/ports/{port}/stop")).status

    async def set_current_limit(self, port: str, amps: int) -> int:
        """Save a current limit in amps. Returns HTTP status."""
        resp = await self._request(
            "PUT", f"/ports/{port}/current_limit", json={"current_limit_a": int(amps)}
        )
        return resp.status
