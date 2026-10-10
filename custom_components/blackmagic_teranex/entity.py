"""Shared entity base for the Blackmagic Teranex integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_MODEL, CONF_SW_VERSION, DOMAIN, MANUFACTURER
from .protocol import (
    BLOCK_DEVICE,
    BLOCK_NETWORK,
    TeranexClient,
    TeranexCommandError,
    TeranexConnectionError,
)

_LOGGER = logging.getLogger(__name__)


class TeranexEntity(Entity):
    """Base entity wired to the push client."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: TeranexClient, entry_id: str, key: str) -> None:
        """Initialise the entity."""
        self._client = client
        self._attr_unique_id = f"{entry_id}_{key}"
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information.

        Live values from the unit win; while it is switched off the identity
        stored in the config entry is used, so the device keeps its details.
        """
        stored: dict[str, str] = {}
        title: str | None = None
        if self.hass is not None and (
            entry := self.hass.config_entries.async_get_entry(self._entry_id)
        ):
            stored = dict(entry.data)
            title = entry.title

        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            manufacturer=MANUFACTURER,
            model=self._client.model or stored.get(CONF_MODEL) or "Teranex",
            name=(
                self._client.get(BLOCK_NETWORK, "Friendly name")
                or stored.get(CONF_NAME)
                or title
            ),
            sw_version=(
                self._client.get(BLOCK_DEVICE, "Software Version")
                or stored.get(CONF_SW_VERSION)
            ),
            configuration_url=f"http://{self._client.host}",
        )

    @property
    def available(self) -> bool:
        """Return whether the connection is up."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to push updates."""
        self.async_on_remove(self._client.add_listener(self.async_write_ha_state))

    async def async_send(self, block: str, fields: dict[str, str]) -> None:
        """Send a command and translate failures into user-facing errors.

        No optimistic state is written. The device reports the new value in a
        status block of its own, which is the only thing that moves an entity.
        """
        try:
            await self._client.async_send(block, fields)
        except TeranexCommandError as err:
            _LOGGER.debug("Teranex rejected %s %s: %s", block, fields, err)
            raise HomeAssistantError(
                f"The Teranex rejected this setting: {fields}. "
                "Your model or firmware may use a different value name."
            ) from err
        except TeranexConnectionError as err:
            raise HomeAssistantError(
                f"The Teranex at {self._client.host} did not respond."
            ) from err
