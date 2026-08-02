"""Sensors for the Blackmagic HyperDeck."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HyperDeckConfigEntry
from .coordinator import HyperDeckCoordinator
from .entity import HyperDeckEntity


@dataclass(frozen=True, kw_only=True)
class HyperDeckSensorDescription(SensorEntityDescription):
    value_fn: Callable[[HyperDeckCoordinator], Any]


def _timecode(c: HyperDeckCoordinator) -> str | None:
    return ((c.data or {}).get("timecode") or {}).get("display")


def _clip_name(c: HyperDeckCoordinator) -> str | None:
    clip = c.current_clip
    return clip.get("filePath") if clip else None


def _transport_mode(c: HyperDeckCoordinator) -> str | None:
    return ((c.data or {}).get("transport") or {}).get("mode")


SENSORS: tuple[HyperDeckSensorDescription, ...] = (
    HyperDeckSensorDescription(
        key="timecode",
        translation_key="timecode",
        icon="mdi:timer-outline",
        value_fn=_timecode,
    ),
    HyperDeckSensorDescription(
        key="current_clip",
        translation_key="current_clip",
        icon="mdi:filmstrip",
        value_fn=_clip_name,
    ),
    HyperDeckSensorDescription(
        key="transport_mode",
        translation_key="transport_mode",
        icon="mdi:video-switch",
        value_fn=_transport_mode,
    ),
    HyperDeckSensorDescription(
        key="clip_progress",
        translation_key="clip_progress",
        icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.clip_progress(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperDeckConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HyperDeckSensor(coordinator, description) for description in SENSORS
    )


class HyperDeckSensor(HyperDeckEntity, SensorEntity):
    entity_description: HyperDeckSensorDescription

    def __init__(
        self,
        coordinator: HyperDeckCoordinator,
        description: HyperDeckSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)
