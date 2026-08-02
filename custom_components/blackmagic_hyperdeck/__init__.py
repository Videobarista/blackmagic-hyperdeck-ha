"""The Blackmagic HyperDeck integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HyperDeckClient
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT
from .coordinator import HyperDeckCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.SWITCH,
]

HyperDeckConfigEntry = ConfigEntry[HyperDeckCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HyperDeckConfigEntry) -> bool:
    """Set up Blackmagic HyperDeck from a config entry."""
    client = HyperDeckClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        async_get_clientsession(hass),
    )
    coordinator = HyperDeckCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    coordinator.start_websocket()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HyperDeckConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.stop_websocket()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
