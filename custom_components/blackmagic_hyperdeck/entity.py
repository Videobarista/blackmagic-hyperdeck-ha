"""Base entity for the Blackmagic HyperDeck integration."""
from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import HyperDeckError
from .const import DOMAIN, MANUFACTURER
from .coordinator import HyperDeckCoordinator

_LOGGER = logging.getLogger(__name__)
_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def suppress_command_errors(func: _F) -> _F:
    """Quietly absorb HyperDeckError from an entity action method.

    The deck rejecting a command outright (e.g. "105 no disk" when
    pressing play/record with no media inserted) or being unreachable is
    an expected, everyday occurrence for hardware like this - not a bug.
    Left uncaught, it reaches HA's service-call machinery as an unhandled
    exception, logged as a full ERROR-level traceback per press, which
    floods the log for something this routine. Logged at debug instead;
    the entity's state simply reflects reality once the next poll or
    push notification comes in, same as if nothing had been pressed.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HyperDeckError as err:
            _LOGGER.debug("HyperDeck action ignored: %s", err)
        return None

    return wrapper  # type: ignore[return-value]


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
