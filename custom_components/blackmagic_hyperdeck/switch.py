"""Loop switches for the Blackmagic HyperDeck."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HyperDeckConfigEntry
from .coordinator import HyperDeckCoordinator
from .entity import HyperDeckEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperDeckConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            HyperDeckPlaybackSwitch(coordinator, "loop", "mdi:repeat"),
            HyperDeckPlaybackSwitch(coordinator, "singleClip", "mdi:repeat-once"),
        ]
    )


class HyperDeckPlaybackSwitch(HyperDeckEntity, SwitchEntity):
    """Toggle a boolean flag of /transports/0/playback (loop / singleClip)."""

    def __init__(
        self, coordinator: HyperDeckCoordinator, flag: str, icon: str
    ) -> None:
        super().__init__(coordinator)
        self._flag = flag
        self._attr_icon = icon
        self._attr_translation_key = "loop" if flag == "loop" else "single_clip"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{flag}"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.playback.get(self._flag))

    async def _set(self, value: bool) -> None:
        await self.coordinator.client.set_playback(**{self._flag: value})
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
