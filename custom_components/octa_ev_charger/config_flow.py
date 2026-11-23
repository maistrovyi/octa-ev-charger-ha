"""UI setup: host, station ID, token; options: polling interval."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import EvApiError, EvAuthError, EvStationApi
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MIN_SCAN_INTERVAL,
)

_TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class EvConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, host: str, station: str, token: str) -> str | None:
        """Return an error key, or None if the API answers."""
        api = EvStationApi(async_get_clientsession(self.hass), host, station, token)
        try:
            await api.get_status()
        except EvAuthError:
            return "invalid_auth"
        except EvApiError as err:
            LOGGER.debug("Validation failed: %s", err)
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            if not host.startswith(("http://", "https://")):
                host = f"https://{host}"
            station = user_input[CONF_STATION_ID].strip()
            token = user_input[CONF_TOKEN].strip()

            await self.async_set_unique_id(f"{host}|{station}".lower())
            self._abort_if_unique_id_configured()

            if not (error := await self._validate(host, station, token)):
                return self.async_create_entry(
                    title=f"EV Station {station}",
                    data={CONF_HOST: host, CONF_STATION_ID: station, CONF_TOKEN: token},
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_STATION_ID): str,
                vol.Required(CONF_TOKEN): _TOKEN_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            error = await self._validate(entry.data[CONF_HOST], entry.data[CONF_STATION_ID], token)
            if not error:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): _TOKEN_SELECTOR}),
            description_placeholders={"station": entry.data[CONF_STATION_ID]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EvOptionsFlow()


class EvOptionsFlow(OptionsFlowWithReload):
    """Polling interval. The entry reloads automatically after saving."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=3600,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
