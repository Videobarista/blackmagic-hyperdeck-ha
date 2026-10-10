"""Shared fixtures for the Blackmagic Teranex tests."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blackmagic_teranex.const import (
    CONF_MODEL,
    CONF_SW_VERSION,
    DOMAIN,
)
from custom_components.blackmagic_teranex.protocol import TeranexConnectionError
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

HOST = "192.168.51.167"
PORT = 9800

# A trimmed copy of a real Teranex 2D state dump.
DEVICE_STATE: dict[str, dict[str, str]] = {
    "PROTOCOL PREAMBLE": {"Version": "1.13"},
    "TERANEX DEVICE": {
        "Model name": "Teranex 2D",
        "Software Version": "0x74e4b2e",
        "FPGA Version": "0x30",
    },
    "NETWORK CONFIG": {"Friendly name": "Studio Teranex", "IP address": "3232248743"},
    "VIDEO INPUT": {"Video source": "SDI1", "Signal present": "true"},
    "VIDEO OUTPUT": {"Video mode": "1080p25", "Aspect ratio": "Anamorphic"},
    "VIDEO PROC AMP": {"Gain": "0"},
    "PRESET": {f"PresetName{index}": f"Preset {index + 1}" for index in range(6)},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


class FakeClient:
    """Stand-in for TeranexClient that never touches the network."""

    instances: list[FakeClient] = []
    online: bool = True

    def __init__(self, host: str, port: int = PORT) -> None:
        """Start in the state the class-level switches describe."""
        self.host = host
        self.port = port
        self.connected = FakeClient.online
        self.state: dict[str, dict[str, str]] = (
            {block: dict(fields) for block, fields in DEVICE_STATE.items()}
            if FakeClient.online
            else {}
        )
        self.sent: list[tuple[str, dict[str, str]]] = []
        self.send_error: Exception | None = None
        self.closed = False
        self._listeners: list[Callable[[], None]] = []
        FakeClient.instances.append(self)

    @property
    def model(self) -> str | None:
        """Return the reported model name."""
        return self.get("TERANEX DEVICE", "Model name")

    def get(self, block: str, key: str) -> str | None:
        """Return one reported value."""
        return self.state.get(block, {}).get(key)

    def block(self, block: str) -> Mapping[str, str]:
        """Return a whole reported block."""
        return self.state.get(block, {})

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener."""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def notify(self) -> None:
        """Fire the listeners, as the real client does after a status block."""
        for callback in list(self._listeners):
            callback()

    async def async_start(self) -> None:
        """Start without blocking, like the real client."""

    async def async_wait_ready(self, timeout: float) -> bool:
        """Report whether the first dump arrived."""
        return self.connected

    async def async_send(self, block: str, fields: Mapping[str, str]) -> None:
        """Record a command, or fail the way the test asks for."""
        if self.send_error is not None:
            raise self.send_error
        if not self.connected:
            raise TeranexConnectionError(f"Not connected to {self.host}")
        self.sent.append((block, dict(fields)))

    async def async_close(self) -> None:
        """Record that the client was closed."""
        self.closed = True


@pytest.fixture
def fake_client() -> Generator[type[FakeClient]]:
    """Replace the protocol client used by the integration."""
    FakeClient.instances = []
    FakeClient.online = True
    with patch("custom_components.blackmagic_teranex.TeranexClient", FakeClient):
        yield FakeClient


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry as the config flow creates it."""
    data: dict[str, Any] = {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_NAME: "Studio Teranex",
        CONF_MODEL: "Teranex 2D",
        CONF_SW_VERSION: "0x74e4b2e",
    }
    return MockConfigEntry(
        domain=DOMAIN,
        title="Studio Teranex",
        unique_id=f"{HOST}:{PORT}",
        data=data,
    )
