"""Tests for the Blackmagic Teranex config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blackmagic_teranex.const import (
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_VIDEO_MODES,
    DOMAIN,
)
from custom_components.blackmagic_teranex.protocol import TeranexConnectionError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_STATE, HOST, PORT


class ProbeClient:
    """Stand-in for the one-shot connection the config flow makes."""

    reachable: bool = True
    closed: int = 0

    def __init__(self, host: str, port: int) -> None:
        """Remember the address."""
        self.host = host
        self.port = port

    async def async_connect_once(self) -> None:
        """Succeed or fail depending on the class switch."""
        if not ProbeClient.reachable:
            raise TeranexConnectionError("unreachable")

    def get(self, block: str, key: str) -> str | None:
        """Return one value from the sample dump."""
        return DEVICE_STATE.get(block, {}).get(key)

    async def async_close(self) -> None:
        """Count closes, which must happen on success and failure alike."""
        ProbeClient.closed += 1


@pytest.fixture(autouse=True)
def probe_client() -> Generator[type[ProbeClient]]:
    """Replace the client the config flow uses."""
    ProbeClient.reachable = True
    ProbeClient.closed = 0
    with patch(
        "custom_components.blackmagic_teranex.config_flow.TeranexClient", ProbeClient
    ):
        yield ProbeClient


@pytest.fixture(autouse=True)
def no_setup() -> Generator[AsyncMock]:
    """Keep the flow tests from setting up the integration itself."""
    with patch(
        "custom_components.blackmagic_teranex.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A reachable unit is added, with its identity stored in the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f" {HOST} ", CONF_PORT: PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Studio Teranex"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_NAME: "Studio Teranex",
        CONF_MODEL: "Teranex 2D",
        CONF_SW_VERSION: "0x74e4b2e",
    }
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    assert ProbeClient.closed == 1


async def test_user_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, probe_client: type[ProbeClient]
) -> None:
    """An unreachable unit shows an error and the user can try again."""
    probe_client.reachable = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert probe_client.closed == 1

    probe_client.reachable = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The same address cannot be added twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_without_friendly_name_uses_model(
    hass: HomeAssistant,
) -> None:
    """A unit without a friendly name is titled after its model."""
    with patch.dict(DEVICE_STATE, {"NETWORK CONFIG": {}}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teranex 2D"
    assert CONF_NAME not in result["data"]


async def test_reconfigure_changes_address(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A new address is stored once the unit answers on it."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.51.200", CONF_PORT: PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "192.168.51.200"
    assert config_entry.unique_id == f"192.168.51.200:{PORT}"
    assert config_entry.data[CONF_MODEL] == "Teranex 2D"


async def test_reconfigure_cannot_connect_keeps_old_address(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    probe_client: type[ProbeClient],
) -> None:
    """A typo or unreachable address never replaces a working one."""
    config_entry.add_to_hass(hass)
    probe_client.reachable = False
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.51.201", CONF_PORT: PORT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert config_entry.data[CONF_HOST] == HOST


async def test_reconfigure_rejects_address_of_other_unit(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Two entries can never end up pointing at the same unit."""
    config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other Teranex",
        unique_id=f"192.168.51.50:{PORT}",
        data={CONF_HOST: "192.168.51.50", CONF_PORT: PORT},
    )
    other.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.51.50", CONF_PORT: PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == HOST


async def test_options_flow_sets_output_formats(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The output format list is stored trimmed and without empty items."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_VIDEO_MODES: " 1080p25, 1080i50 ,, "}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_VIDEO_MODES: ["1080p25", "1080i50"]}
