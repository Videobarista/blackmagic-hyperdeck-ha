"""Switches for the Blackmagic Teranex integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeranexConfigEntry
from .entity import TeranexEntity
from .protocol import (
    BLOCK_ANCILLARY,
    BLOCK_NOISE_REDUCTION,
    BLOCK_VIDEO_INPUT,
    TeranexClient,
)


@dataclass(frozen=True, kw_only=True)
class TeranexSwitchDescription(SwitchEntityDescription):
    """Describes a Teranex switch."""

    block: str
    field: str


SWITCHES: tuple[TeranexSwitchDescription, ...] = (
    TeranexSwitchDescription(
        key="auto_detection",
        translation_key="auto_detection",
        block=BLOCK_VIDEO_INPUT,
        field="Auto detection enabled",
    ),
    TeranexSwitchDescription(
        key="noise_reduction",
        translation_key="noise_reduction",
        block=BLOCK_NOISE_REDUCTION,
        field="Enabled",
    ),
    TeranexSwitchDescription(
        key="noise_reduction_split_screen",
        translation_key="noise_reduction_split_screen",
        block=BLOCK_NOISE_REDUCTION,
        field="Split screen",
        entity_registry_enabled_default=False,
    ),
    TeranexSwitchDescription(
        key="noise_reduction_red_overlay",
        translation_key="noise_reduction_red_overlay",
        block=BLOCK_NOISE_REDUCTION,
        field="Red overlay",
        entity_registry_enabled_default=False,
    ),
    TeranexSwitchDescription(
        key="closed_captioning",
        translation_key="closed_captioning",
        block=BLOCK_ANCILLARY,
        field="CC enabled",
    ),
    TeranexSwitchDescription(
        key="wide_sd_aspect",
        translation_key="wide_sd_aspect",
        block=BLOCK_VIDEO_INPUT,
        field="Wide SD aspect",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeranexConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches."""
    client = entry.runtime_data
    async_add_entities(
        TeranexSwitch(client, entry.entry_id, description) for description in SWITCHES
    )


class TeranexSwitch(TeranexEntity, SwitchEntity):
    """A boolean setting the device both reports and accepts."""

    entity_description: TeranexSwitchDescription

    def __init__(
        self,
        client: TeranexClient,
        entry_id: str,
        description: TeranexSwitchDescription,
    ) -> None:
        """Initialise the switch."""
        super().__init__(client, entry_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state the device last reported."""
        raw = self._client.get(
            self.entity_description.block, self.entity_description.field
        )
        if raw is None:
            return None
        return raw.strip().lower() == "true"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self._async_set("true")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self._async_set("false")

    async def _async_set(self, value: str) -> None:
        """Send the new value; the device reports the result itself."""
        await self.async_send(
            self.entity_description.block, {self.entity_description.field: value}
        )
