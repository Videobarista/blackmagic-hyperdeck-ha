"""Timecode generator values for the Blackmagic Teranex integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeranexConfigEntry
from .entity import TeranexEntity
from .protocol import BLOCK_ANCILLARY, TeranexClient

# HH:MM:SS:FF, where the device uses a semicolon before the frames in drop
# frame formats.
TIMECODE_PATTERN = r"^\d{2}:\d{2}:\d{2}[:;]\d{2}$"


@dataclass(frozen=True, kw_only=True)
class TeranexTextDescription(TextEntityDescription):
    """Describes a Teranex text control."""

    block: str
    field: str


TEXTS: tuple[TeranexTextDescription, ...] = (
    TeranexTextDescription(
        key="timecode_generate_value",
        translation_key="timecode_generate_value",
        block=BLOCK_ANCILLARY,
        field="Timecode generate value",
        native_min=11,
        native_max=11,
        pattern=TIMECODE_PATTERN,
        entity_category=EntityCategory.CONFIG,
    ),
    TeranexTextDescription(
        key="timecode_jam_sync_value",
        translation_key="timecode_jam_sync_value",
        block=BLOCK_ANCILLARY,
        field="Timecode jam sync value",
        native_min=11,
        native_max=11,
        pattern=TIMECODE_PATTERN,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeranexConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the timecode text controls."""
    client = entry.runtime_data
    async_add_entities(
        TeranexText(client, entry.entry_id, description) for description in TEXTS
    )


class TeranexText(TeranexEntity, TextEntity):
    """A timecode value the device both reports and accepts."""

    entity_description: TeranexTextDescription

    def __init__(
        self,
        client: TeranexClient,
        entry_id: str,
        description: TeranexTextDescription,
    ) -> None:
        """Initialise the text entity."""
        super().__init__(client, entry_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        """Return the timecode the device last reported."""
        return self._client.get(
            self.entity_description.block, self.entity_description.field
        )

    async def async_set_value(self, value: str) -> None:
        """Send the new timecode."""
        await self.async_send(
            self.entity_description.block, {self.entity_description.field: value}
        )
