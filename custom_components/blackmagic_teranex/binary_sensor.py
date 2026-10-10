"""Binary sensors for the Blackmagic Teranex integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeranexConfigEntry
from .entity import TeranexEntity
from .protocol import (
    BLOCK_GENLOCK,
    BLOCK_VIDEO_INPUT,
    BLOCK_VIDEO_OUTPUT,
    TeranexClient,
)


def _is_true(value: str) -> bool:
    """Interpret the device's boolean spelling."""
    return value.strip().lower() == "true"


def _is_detected(value: str) -> bool:
    """Interpret the device's Detected/None spelling."""
    return value.strip().lower() == "detected"


@dataclass(frozen=True, kw_only=True)
class TeranexBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Teranex binary sensor."""

    block: str
    field: str
    is_on: Callable[[str], bool] = _is_true


BINARY_SENSORS: tuple[TeranexBinarySensorDescription, ...] = (
    TeranexBinarySensorDescription(
        key="signal_present",
        translation_key="signal_present",
        block=BLOCK_VIDEO_INPUT,
        field="Signal present",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeranexBinarySensorDescription(
        key="genlock_locked",
        translation_key="genlock_locked",
        block=BLOCK_GENLOCK,
        field="Signal locked",
    ),
    TeranexBinarySensorDescription(
        key="timecode_present",
        translation_key="timecode_present",
        block=BLOCK_VIDEO_INPUT,
        field="Timecode present",
        is_on=_is_detected,
    ),
    TeranexBinarySensorDescription(
        key="closed_captioning_present",
        translation_key="closed_captioning_present",
        block=BLOCK_VIDEO_INPUT,
        field="Closed captioning present",
        is_on=_is_detected,
    ),
    TeranexBinarySensorDescription(
        key="still_frame_present",
        translation_key="still_frame_present",
        block=BLOCK_VIDEO_OUTPUT,
        field="Still frame present",
        entity_registry_enabled_default=False,
    ),
    TeranexBinarySensorDescription(
        key="optical_module_present",
        translation_key="optical_module_present",
        block=BLOCK_VIDEO_INPUT,
        field="Optical module present",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeranexConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    client = entry.runtime_data
    entities: list[BinarySensorEntity] = [TeranexConnectionSensor(client, entry.entry_id)]
    entities.extend(
        TeranexBinarySensor(client, entry.entry_id, description)
        for description in BINARY_SENSORS
    )
    async_add_entities(entities)


class TeranexConnectionSensor(TeranexEntity, BinarySensorEntity):
    """Whether Home Assistant can reach the unit.

    Unlike every other entity this one stays available while the unit is
    switched off, so the device page reads "Disconnected" rather than a wall
    of unavailable entities with no explanation.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connection"

    def __init__(self, client: TeranexClient, entry_id: str) -> None:
        """Initialise the connection sensor."""
        super().__init__(client, entry_id, "connection")

    @property
    def available(self) -> bool:
        """Always available; the state itself says whether the unit is reachable."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the connection to the unit is up."""
        return self._client.connected


class TeranexBinarySensor(TeranexEntity, BinarySensorEntity):
    """A read-only true/false value reported by the device."""

    entity_description: TeranexBinarySensorDescription

    def __init__(
        self,
        client: TeranexClient,
        entry_id: str,
        description: TeranexBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(client, entry_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state, or None if the device never reported it."""
        raw = self._client.get(
            self.entity_description.block, self.entity_description.field
        )
        if raw is None:
            return None
        return self.entity_description.is_on(raw)
