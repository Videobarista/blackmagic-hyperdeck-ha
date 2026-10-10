"""The Blackmagic Teranex integration."""

from __future__ import annotations

from collections.abc import Callable
import logging

import voluptuous as vol

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_PRESET,
    CONF_MODEL,
    CONF_SW_VERSION,
    DEFAULT_PORT,
    DOMAIN,
    SERVICE_SAVE_PRESET,
    SETUP_GRACE_PERIOD,
)
from .protocol import BLOCK_DEVICE, BLOCK_NETWORK, TeranexClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

PRESET_COUNT = 6

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TeranexConfigEntry = ConfigEntry[TeranexClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions.

    Actions are registered here rather than per config entry, so automations
    that use them still validate while a Teranex is not loaded.
    """
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SAVE_PRESET,
        entity_domain=SELECT_DOMAIN,
        schema={
            vol.Required(ATTR_PRESET): vol.All(
                cv.positive_int, vol.Range(min=1, max=PRESET_COUNT)
            )
        },
        func="async_save_preset",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TeranexConfigEntry) -> bool:
    """Set up a Teranex, whether or not it is currently switched on.

    A Teranex in a studio rack is often powered down by a switched outlet.
    Setup therefore never fails on an unreachable unit: the entities are
    created straight away, show as unavailable, and come to life as soon as
    the unit answers. The client keeps retrying in the background.
    """
    client = TeranexClient(
        entry.data[CONF_HOST], entry.data.get(CONF_PORT, DEFAULT_PORT)
    )
    await client.async_start()
    await client.async_wait_ready(SETUP_GRACE_PERIOD)

    entry.runtime_data = client
    entry.async_on_unload(client.add_listener(_identity_listener(hass, entry)))

    options_at_setup = dict(entry.options)

    async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload when the options change.

        The stored identity of the unit also lives in the entry and changes
        on connect; those updates must not trigger a reload.
        """
        if dict(entry.options) != options_at_setup:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeranexConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded


def _identity_listener(
    hass: HomeAssistant, entry: TeranexConfigEntry
) -> Callable[[], None]:
    """Keep the stored identity of the unit in step with what it reports.

    Whenever the unit reports a different name, model or firmware, the config
    entry and the device registry are updated, so the next start while the
    unit is switched off still shows the right details.
    """

    @callback
    def _async_update_identity() -> None:
        client = entry.runtime_data
        reported = {
            CONF_NAME: client.get(BLOCK_NETWORK, "Friendly name"),
            CONF_MODEL: client.get(BLOCK_DEVICE, "Model name"),
            CONF_SW_VERSION: client.get(BLOCK_DEVICE, "Software Version"),
        }
        changes = {
            key: value
            for key, value in reported.items()
            if value and entry.data.get(key) != value
        }
        if not changes:
            return

        hass.config_entries.async_update_entry(entry, data={**entry.data, **changes})

        registry = dr.async_get(hass)
        device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        if device is not None:
            registry.async_update_device(
                device.id,
                name=entry.data.get(CONF_NAME),
                model=entry.data.get(CONF_MODEL),
                sw_version=entry.data.get(CONF_SW_VERSION),
            )

    return _async_update_identity
