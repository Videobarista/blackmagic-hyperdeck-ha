"""Config flow for the Blackmagic HyperDeck integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import HyperDeckClient, HyperDeckConnectionError, HyperDeckError
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class HyperDeckConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 2  # bumped: v1 config entries pointed at the REST port (80)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            client = HyperDeckClient(host, port)
            try:
                banner = await client.connect()
                await client.disconnect()
            except HyperDeckConnectionError:
                errors["base"] = "cannot_connect"
            except HyperDeckError:
                errors["base"] = "unknown"
            else:
                title = banner.params.get("model") or f"HyperDeck ({host})"
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
