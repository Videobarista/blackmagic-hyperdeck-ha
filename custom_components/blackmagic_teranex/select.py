"""Selects for the Blackmagic Teranex integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeranexConfigEntry
from .const import (
    AFD_INSERT_TYPES,
    ANALOG_OUTPUTS,
    ASPECT_RATIOS,
    AUDIO_CHANNELS,
    AUDIO_ROUTING_SOURCES,
    AUDIO_SOURCES,
    CONF_VIDEO_MODES,
    DEFAULT_VIDEO_MODES,
    NO_SIGNAL_OUTPUTS,
    TEST_PATTERNS,
    TIMECODE_DROP_FRAME,
    TIMECODE_MODES,
    TIMECODE_START_SOURCES,
    VIDEO_SOURCES,
)
from .entity import TeranexEntity
from .protocol import (
    BLOCK_ANCILLARY,
    BLOCK_AUDIO,
    BLOCK_PRESET,
    BLOCK_TEST_PATTERN,
    BLOCK_VIDEO_INPUT,
    BLOCK_VIDEO_OUTPUT,
    TeranexClient,
)

_LOGGER = logging.getLogger(__name__)

PRESET_COUNT = 6  # The Teranex has six preset slots.


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeranexConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the selects."""
    client = entry.runtime_data

    configured = entry.options.get(CONF_VIDEO_MODES)
    video_modes = tuple(configured) if configured else DEFAULT_VIDEO_MODES

    entities: list[TeranexEntity] = [
        TeranexSelect(
            client,
            entry.entry_id,
            key="video_source",
            name="Video input",
            block=BLOCK_VIDEO_INPUT,
            field="Video source",
            options=VIDEO_SOURCES,
            icon="mdi:import",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="audio_source",
            name="Audio source",
            block=BLOCK_VIDEO_INPUT,
            field="Audio source",
            options=AUDIO_SOURCES,
            icon="mdi:volume-high",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="video_mode",
            name="Output format",
            block=BLOCK_VIDEO_OUTPUT,
            field="Video mode",
            options=video_modes,
            icon="mdi:television",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="aspect_ratio",
            name="Output aspect ratio",
            block=BLOCK_VIDEO_OUTPUT,
            field="Aspect ratio",
            options=ASPECT_RATIOS,
            icon="mdi:aspect-ratio",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="analog_output",
            name="Output analogue",
            block=BLOCK_VIDEO_OUTPUT,
            field="Analog output",
            options=ANALOG_OUTPUTS,
            icon="mdi:video-output",
            enabled_default=False,
            category=EntityCategory.CONFIG,
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="test_pattern",
            name="Test pattern",
            block=BLOCK_TEST_PATTERN,
            field="Output",
            options=TEST_PATTERNS,
            icon="mdi:test-tube",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="no_signal_output",
            name="Test pattern on signal loss",
            block=BLOCK_TEST_PATTERN,
            field="No signal",
            options=NO_SIGNAL_OUTPUTS,
            icon="mdi:video-off",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="timecode_mode",
            name="Timecode mode",
            block=BLOCK_ANCILLARY,
            field="Timecode mode",
            options=TIMECODE_MODES,
            icon="mdi:timer-outline",
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="timecode_start_source",
            name="Timecode start source",
            block=BLOCK_ANCILLARY,
            field="Timecode start source",
            options=TIMECODE_START_SOURCES,
            icon="mdi:timer-cog-outline",
            category=EntityCategory.CONFIG,
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="timecode_drop_frame",
            name="Timecode drop frame",
            block=BLOCK_ANCILLARY,
            field="Timecode drop frame mode",
            options=TIMECODE_DROP_FRAME,
            icon="mdi:timer-sand",
            enabled_default=False,
            category=EntityCategory.CONFIG,
        ),
        TeranexSelect(
            client,
            entry.entry_id,
            key="afd_insert_type",
            name="AFD insert",
            block=BLOCK_ANCILLARY,
            field="AFD insert type",
            options=AFD_INSERT_TYPES,
            icon="mdi:crop",
            enabled_default=False,
            category=EntityCategory.CONFIG,
        ),
        TeranexPresetSelect(client, entry.entry_id),
    ]

    # Audio routing. AudioOut0 is output channel 1, and so on.
    entities.extend(
        TeranexSelect(
            client,
            entry.entry_id,
            key=f"audio_out_{channel}",
            name=f"Audio output {channel + 1}",
            block=BLOCK_AUDIO,
            field=f"AudioOut{channel}",
            options=AUDIO_ROUTING_SOURCES,
            icon="mdi:call-split",
            enabled_default=channel < 2,
        )
        for channel in range(AUDIO_CHANNELS)
    )
    async_add_entities(entities)


class TeranexSelect(TeranexEntity, SelectEntity):
    """A setting with a fixed set of values.

    The documented value list is not always what a given model and firmware
    actually use, so whatever the device currently reports is merged into the
    options. That keeps the entity usable even when the manual is wrong.
    """

    def __init__(
        self,
        client: TeranexClient,
        entry_id: str,
        *,
        key: str,
        name: str,
        block: str,
        field: str,
        options: tuple[str, ...],
        icon: str | None = None,
        enabled_default: bool = True,
        category: EntityCategory | None = None,
    ) -> None:
        """Initialise the select."""
        super().__init__(client, entry_id, key)
        self._block = block
        self._field = field
        self._base_options = options
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_entity_category = category

    @property
    def options(self) -> list[str]:
        """Return the documented options plus whatever the device reports."""
        options = list(self._base_options)
        current = self._client.get(self._block, self._field)
        if current and current not in options:
            options.append(current)
        return options

    @property
    def current_option(self) -> str | None:
        """Return the value the device last reported."""
        return self._client.get(self._block, self._field)

    async def async_select_option(self, option: str) -> None:
        """Send the new value; the device reports the result itself."""
        await self.async_send(self._block, {self._field: option})

    async def async_save_preset(self, preset: int) -> None:
        """Ignore save_preset aimed at this entity.

        The action is registered for every Teranex select, so targeting a
        whole device reaches all of them. Only the Preset entity acts on it.
        """


class TeranexPresetSelect(TeranexEntity, SelectEntity):
    """Recall one of the six presets.

    The device never reports which preset is active, so this entity shows the
    last preset recalled through Home Assistant and nothing else. Recall it
    from the front panel and this goes back to unknown, which is honest: the
    protocol simply does not say.
    """

    _attr_name = "Preset"
    _attr_icon = "mdi:playlist-play"

    def __init__(self, client: TeranexClient, entry_id: str) -> None:
        """Initialise the preset select."""
        super().__init__(client, entry_id, "preset")
        self._last_recalled: str | None = None

    def _preset_names(self) -> list[str]:
        """Return the six preset names as the device stores them."""
        block = self._client.block(BLOCK_PRESET)
        return [
            block.get(f"PresetName{index}") or f"Preset {index + 1}"
            for index in range(PRESET_COUNT)
        ]

    @property
    def options(self) -> list[str]:
        """Return the preset names."""
        return self._preset_names()

    @property
    def current_option(self) -> str | None:
        """Return the last preset recalled from Home Assistant, if any."""
        if self._last_recalled in self._preset_names():
            return self._last_recalled
        return None

    async def async_select_option(self, option: str) -> None:
        """Recall the chosen preset."""
        names = self._preset_names()
        if option not in names:
            raise HomeAssistantError(f"Unknown preset: {option}")
        number = names.index(option) + 1
        await self.async_send(BLOCK_PRESET, {"Recall": str(number)})
        self._last_recalled = option
        self.async_write_ha_state()

    async def async_save_preset(self, preset: int) -> None:
        """Overwrite a preset with the current device settings."""
        await self.async_send(BLOCK_PRESET, {"Save": str(preset)})
        _LOGGER.debug("Teranex %s saved preset %s", self._client.host, preset)
