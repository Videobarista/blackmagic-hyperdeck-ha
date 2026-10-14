"""Tests for the Blackmagic HyperDeck config flow."""

from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blackmagic_hyperdeck.api import (
    HyperDeckConnectionError,
    HyperDeckError,
    HyperDeckResponse,
)
from custom_components.blackmagic_hyperdeck.const import CONF_HOST, CONF_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, PORT, USER_INPUT


async def test_user_flow_success(
    hass: HomeAssistant, mock_flow_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """A reachable deck creates an entry titled after the model in its banner."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f"  {HOST} ", CONF_PORT: PORT}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HyperDeck Studio Pro"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    mock_flow_client.connect.assert_awaited_once()
    mock_flow_client.disconnect.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_title_fallback(
    hass: HomeAssistant, mock_flow_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """A banner without a model falls back to a host-based title."""
    mock_flow_client.connect.return_value = HyperDeckResponse(
        code=500, text="connection info", params={}
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"HyperDeck ({HOST})"


async def test_user_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, mock_flow_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """An unreachable deck shows an error; the user can retry once it is on."""
    mock_flow_client.connect.side_effect = HyperDeckConnectionError("unreachable")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_flow_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_flow_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Any other HyperDeck error is reported as unknown."""
    mock_flow_client.connect.side_effect = HyperDeckError("unexpected")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same host and port cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_flow_client.connect.assert_not_awaited()
