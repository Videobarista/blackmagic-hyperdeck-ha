"""The Blackmagic HyperDeck integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import HyperDeckError
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
    coordinator = HyperDeckCoordinator(
        hass,
        entry,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    try:
        await coordinator.async_setup()
    except HyperDeckError as err:
        raise ConfigEntryNotReady(
            f"Cannot reach HyperDeck at {coordinator.client.host}:{coordinator.client.port}: {err}"
        ) from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HyperDeckConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
