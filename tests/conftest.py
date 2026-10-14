"""Shared fixtures for the Blackmagic HyperDeck tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blackmagic_hyperdeck.api import (
    HyperDeckConnectionError,
    HyperDeckResponse,
)
from custom_components.blackmagic_hyperdeck.const import CONF_HOST, CONF_PORT, DOMAIN

HOST = "10.0.0.50"
PORT = 9993
USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT}
BANNER = HyperDeckResponse(
    code=500,
    text="connection info",
    params={"protocol version": "1.8", "model": "HyperDeck Studio Pro"},
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration from custom_components."""
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry as created by the config flow (flow VERSION 2)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HyperDeck Studio Pro",
        data=USER_INPUT,
        unique_id=f"{HOST}:{PORT}",
        version=2,
    )


@pytest.fixture
def mock_flow_client() -> Generator[MagicMock]:
    """HyperDeck client used by the config flow, answering with a banner."""
    with patch(
        "custom_components.blackmagic_hyperdeck.config_flow.HyperDeckClient"
    ) as client_cls:
        client = client_cls.return_value
        client.connect = AsyncMock(return_value=BANNER)
        client.disconnect = AsyncMock()
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip real setup when the config flow creates an entry."""
    with patch(
        "custom_components.blackmagic_hyperdeck.async_setup_entry",
        return_value=True,
    ) as setup_entry:
        yield setup_entry


def _coordinator_client(*, reachable: bool) -> MagicMock:
    """Build a fake client for the coordinator."""
    client = MagicMock()
    client.host = HOST
    client.port = PORT
    client.connected = reachable
    if reachable:
        client.connect = AsyncMock(return_value=BANNER)
    else:
        client.connect = AsyncMock(
            side_effect=HyperDeckConnectionError(
                f"Cannot reach HyperDeck at {HOST}:{PORT}: [Errno 113] Connect call failed"
            )
        )
    client.disconnect = AsyncMock()
    client.enable_notifications = AsyncMock()
    client.get_transport_info = AsyncMock(
        return_value={
            "status": "play",
            "speed": "100",
            "clip id": "1",
            "loop": "false",
            "single clip": "false",
            "video format": "1080p24",
            "timecode": "00:00:10:00",
        }
    )
    client.get_slot_info = AsyncMock(return_value={"slot id": "1", "status": "mounted"})
    client.get_configuration = AsyncMock(return_value={"timecode output": "clip"})
    client.get_clips = AsyncMock(
        return_value=[
            {
                "clip_id": 1,
                "name": "Show open.mov",
                "start_timecode": "00:00:00:00",
                "duration_timecode": "00:01:00:00",
                "in_timecode": None,
                "out_timecode": None,
            }
        ]
    )
    return client


@pytest.fixture
def mock_online_deck() -> Generator[MagicMock]:
    """A HyperDeck that is switched on and reachable."""
    client = _coordinator_client(reachable=True)
    with patch(
        "custom_components.blackmagic_hyperdeck.coordinator.HyperDeckClient",
        return_value=client,
    ):
        yield client


@pytest.fixture
def mock_offline_deck() -> Generator[MagicMock]:
    """A HyperDeck that is switched off (connection refused/unreachable)."""
    client = _coordinator_client(reachable=False)
    with patch(
        "custom_components.blackmagic_hyperdeck.coordinator.HyperDeckClient",
        return_value=client,
    ):
        yield client
