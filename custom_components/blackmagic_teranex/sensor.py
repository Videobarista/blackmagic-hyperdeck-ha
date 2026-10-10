"""Diagnostic sensors for the Blackmagic Teranex integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ipaddress
import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeranexConfigEntry
from .entity import TeranexEntity
from .protocol import (
    BLOCK_DEVICE,
    BLOCK_NETWORK,
    BLOCK_PREAMBLE,
    BLOCK_VIDEO_INPUT,
    TeranexClient,
)

_LOGGER = logging.getLogger(__name__)


def _decode_ip(value: str) -> str | None:
    """Turn the device's 32-bit integer notation into dotted quad."""
    try:
        return str(ipaddress.IPv4Address(int(value)))
    except (ValueError, ipaddress.AddressValueError):
        _LOGGER.debug("Cannot decode %r as an IPv4 address", value)
        return None


@dataclass(frozen=True, kw_only=True)
class TeranexSensorDescription(SensorEntityDescription):
    """Describes a Teranex sensor."""

    block: str
    field: str
    transform: Callable[[str], str | None] | None = None


SENSORS: tuple[TeranexSensorDescription, ...] = (
    TeranexSensorDescription(
        key="model_name",
        translation_key="model_name",
        block=BLOCK_DEVICE,
        field="Model name",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeranexSensorDescription(
        key="software_version",
        translation_key="software_version",
        block=BLOCK_DEVICE,
        field="Software Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeranexSensorDescription(
        key="fpga_version",
        translation_key="fpga_version",
        block=BLOCK_DEVICE,
        field="FPGA Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeranexSensorDescription(
        key="protocol_version",
        translation_key="protocol_version",
        block=BLOCK_PREAMBLE,
        field="Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeranexSensorDescription(
        key="friendly_name",
        translation_key="friendly_name",
        block=BLOCK_NETWORK,
        field="Friendly name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeranexSensorDescription(
        key="input_video_mode",
        translation_key="input_video_mode",
        block=BLOCK_VIDEO_INPUT,
        field="Video mode",
    ),
    TeranexSensorDescription(
        key="input_pixel_format",
        translation_key="input_pixel_format",
        block=BLOCK_VIDEO_INPUT,
        field="Video pixel format",
        entity_registry_enabled_default=False,
    ),
    TeranexSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        block=BLOCK_NETWORK,
        field="IP address",
        transform=_decode_ip,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeranexConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diagnostic sensors."""
    client = entry.runtime_data
    async_add_entities(
        TeranexSensor(client, entry.entry_id, description) for description in SENSORS
    )


class TeranexSensor(TeranexEntity, SensorEntity):
    """A single value read straight from the device state."""

    entity_description: TeranexSensorDescription

    def __init__(
        self,
        client: TeranexClient,
        entry_id: str,
        description: TeranexSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(client, entry_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        """Return the current value, or None if the device never sent it."""
        raw = self._client.get(
            self.entity_description.block, self.entity_description.field
        )
        if raw is None:
            return None
        if self.entity_description.transform:
            return self.entity_description.transform(raw)
        return raw
