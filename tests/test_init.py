"""Tests for setting up and unloading the Blackmagic HyperDeck integration."""

import contextlib
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.blackmagic_hyperdeck.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    if entity_id is None:
        raise AssertionError(f"No {platform} entity with unique_id {unique_id}")
    return entity_id


async def test_setup_and_unload_online(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_online_deck: MagicMock
) -> None:
    """A reachable deck loads, reports its state and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    entry_id = mock_config_entry.entry_id
    player = hass.states.get(_entity_id(hass, "media_player", f"{entry_id}_media_player"))
    assert player.state == "playing"
    assert player.attributes["media_title"] == "Show open.mov"
    timecode = hass.states.get(_entity_id(hass, "sensor", f"{entry_id}_timecode"))
    assert timecode.state == "00:00:10:00"

    assert await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_online_deck.disconnect.assert_awaited()


async def test_setup_with_deck_switched_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_offline_deck: MagicMock
) -> None:
    """A deck that is off at startup must not fail setup: it shows as off."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    entry_id = mock_config_entry.entry_id
    player = hass.states.get(_entity_id(hass, "media_player", f"{entry_id}_media_player"))
    assert player.state == STATE_OFF
    timecode = hass.states.get(_entity_id(hass, "sensor", f"{entry_id}_timecode"))
    assert timecode.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_seek_is_kept_inside_the_clip(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_online_deck: MagicMock
) -> None:
    """Seeking past the end lands on the clip's end; infinity is ignored."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    player_id = _entity_id(hass, "media_player", f"{mock_config_entry.entry_id}_media_player")

    await hass.services.async_call(
        "media_player",
        "media_seek",
        {"entity_id": player_id, "seek_position": 1_000_000},
        blocking=True,
    )
    # The 1-minute clip at 24 fps ends at 00:01:00:00.
    mock_online_deck.goto_timecode.assert_awaited_once_with("00:01:00:00")

    mock_online_deck.goto_timecode.reset_mock()
    # Depending on the Home Assistant version, the service schema may already
    # reject infinity; either way no seek command may reach the deck.
    with contextlib.suppress(vol.Invalid):
        await hass.services.async_call(
            "media_player",
            "media_seek",
            {"entity_id": player_id, "seek_position": float("inf")},
            blocking=True,
        )
    mock_online_deck.goto_timecode.assert_not_awaited()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
