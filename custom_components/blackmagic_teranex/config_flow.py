"""Config flow for the Blackmagic Teranex integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_VIDEO_MODES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_VIDEO_MODES,
    DOMAIN,
)
from .protocol import BLOCK_DEVICE, BLOCK_NETWORK, TeranexClient, TeranexConnectionError

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


def _unique_id(host: str, port: int) -> str:
    """Build the unique ID for a host and port.

    The Teranex reports no serial number or MAC address over its protocol, so
    the address is the only stable identifier available. Entities are keyed
    on the config entry ID instead, which is why changing the address through
    reconfigure keeps every entity, its history and its automations intact.
    """
    return f"{host}:{port}"


async def _async_probe(host: str, port: int) -> dict[str, str]:
    """Connect once, read the initial dump and return the unit's identity.

    The identity is stored in the config entry, so the device keeps its name,
    model and firmware in Home Assistant while the unit is switched off.
    Raises TeranexConnectionError when the device cannot be reached.
    """
    client = TeranexClient(host, port)
    try:
        await client.async_connect_once()
        identity = {
            CONF_NAME: client.get(BLOCK_NETWORK, "Friendly name"),
            CONF_MODEL: client.get(BLOCK_DEVICE, "Model name"),
            CONF_SW_VERSION: client.get(BLOCK_DEVICE, "Software Version"),
        }
    finally:
        await client.async_close()
    return {key: value for key, value in identity.items() if value}


class TeranexConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TeranexOptionsFlow:
        """Return the options flow."""
        return TeranexOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the host and verify we can talk to it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            await self.async_set_unique_id(_unique_id(host, port))
            self._abort_if_unique_id_configured()

            try:
                identity = await _async_probe(host, port)
            except TeranexConnectionError:
                errors["base"] = "cannot_connect"
            else:
                title = identity.get(CONF_NAME) or identity.get(CONF_MODEL) or DEFAULT_NAME
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port, **identity},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an existing Teranex.

        Reached through the three-dot menu on the integration entry. The new
        address is only stored after a successful connection, so a typo can
        never leave a working entry pointing at nothing.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            new_unique_id = _unique_id(host, port)

            if self._is_in_use_by_other_entry(entry, new_unique_id):
                return self.async_abort(reason="already_configured")

            try:
                identity = await _async_probe(host, port)
            except TeranexConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=new_unique_id,
                    data_updates={CONF_HOST: host, CONF_PORT: port, **identity},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or dict(entry.data)
            ),
            errors=errors,
        )

    def _is_in_use_by_other_entry(self, entry: ConfigEntry, unique_id: str) -> bool:
        """Return True when another entry already owns this address."""
        return any(
            other.unique_id == unique_id and other.entry_id != entry.entry_id
            for other in self._async_current_entries(include_ignore=False)
        )


class TeranexOptionsFlow(OptionsFlow):
    """Let the user narrow the list of output formats."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the output format list as comma separated values."""
        if user_input is not None:
            modes = [
                mode.strip()
                for mode in user_input[CONF_VIDEO_MODES].split(",")
                if mode.strip()
            ]
            return self.async_create_entry(data={CONF_VIDEO_MODES: modes})

        current = self.config_entry.options.get(
            CONF_VIDEO_MODES, list(DEFAULT_VIDEO_MODES)
        )
        schema = vol.Schema(
            {vol.Required(CONF_VIDEO_MODES, default=", ".join(current)): str}
        )
        return self.async_show_form(step_id="init", data_schema=schema)
