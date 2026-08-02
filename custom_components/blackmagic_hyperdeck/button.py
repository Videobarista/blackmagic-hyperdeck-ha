"""Transport buttons for the Blackmagic HyperDeck."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HyperDeckConfigEntry
from .coordinator import HyperDeckCoordinator
from .entity import HyperDeckEntity


@dataclass(frozen=True, kw_only=True)
class HyperDeckButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[HyperDeckCoordinator], Awaitable[None]]


BUTTONS: tuple[HyperDeckButtonDescription, ...] = (
    HyperDeckButtonDescription(
        key="play",
        translation_key="play",
        icon="mdi:play",
        press_fn=lambda c: c.client.play(),
    ),
    HyperDeckButtonDescription(
        key="stop",
        translation_key="stop",
        icon="mdi:stop",
        press_fn=lambda c: c.client.stop(),
    ),
    HyperDeckButtonDescription(
        key="record",
        translation_key="record",
        icon="mdi:record-rec",
        press_fn=lambda c: c.client.record(),
    ),
    HyperDeckButtonDescription(
        key="next_clip",
        translation_key="next_clip",
        icon="mdi:skip-next",
        press_fn=lambda c: c.async_next_clip(),
    ),
    HyperDeckButtonDescription(
        key="previous_clip",
        translation_key="previous_clip",
        icon="mdi:skip-previous",
        press_fn=lambda c: c.async_previous_clip(),
    ),
    HyperDeckButtonDescription(
        key="restart_clip",
        translation_key="restart_clip",
        icon="mdi:restart",
        press_fn=lambda c: c.async_restart_clip(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperDeckConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HyperDeckButton(coordinator, description) for description in BUTTONS
    )


class HyperDeckButton(HyperDeckEntity, ButtonEntity):
    entity_description: HyperDeckButtonDescription

    def __init__(
        self,
        coordinator: HyperDeckCoordinator,
        description: HyperDeckButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
        await self.coordinator.async_request_refresh()
