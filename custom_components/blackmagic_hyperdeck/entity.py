"""Base entity for the Blackmagic HyperDeck integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HyperDeckCoordinator


class HyperDeckEntity(CoordinatorEntity[HyperDeckCoordinator]):
    """Common device info and coordinator wiring."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HyperDeckCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=device.get("model") or "HyperDeck",
            sw_version=device.get("software version"),
        )
