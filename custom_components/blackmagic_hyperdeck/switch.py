"""Loop switches for the Blackmagic HyperDeck.

The Ethernet Protocol has no command that sets "loop" or "single clip" on
their own - both are parameters of "play" itself (see the "Command
Combinations" section of the protocol doc). So flipping either switch
here re-issues "play" with the deck's other current settings passed
through unchanged, including its current speed - specifically so that
toggling a switch while the deck is stopped doesn't start playback as a
side effect. This is a real limitation of the protocol, not a bug: there
is no way to change these two flags without going through "play".
"""
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
            HyperDeckLoopSwitch(coordinator, "loop", "mdi:repeat"),
            HyperDeckLoopSwitch(coordinator, "single_clip", "mdi:repeat-once"),
        ]
    )


class HyperDeckLoopSwitch(HyperDeckEntity, SwitchEntity):
    """Toggle the deck's "loop" or "single clip" playback flag."""

    def __init__(
        self, coordinator: HyperDeckCoordinator, flag: str, icon: str
    ) -> None:
        super().__init__(coordinator)
        self._flag = flag
        self._attr_icon = icon
        self._attr_translation_key = flag
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{flag}"

    @property
    def is_on(self) -> bool:
        c = self.coordinator
        return c.single_clip if self._flag == "single_clip" else c.loop

    async def _set(self, value: bool) -> None:
        c = self.coordinator
        loop = value if self._flag == "loop" else c.loop
        single_clip = value if self._flag == "single_clip" else c.single_clip
        await c.client.play(loop=loop, single_clip=single_clip, speed=c.speed)
        await c.async_refresh_transport()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
