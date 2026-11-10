"""The integration only talks to the configured HyperDeck.

The runtime half of the "Local only" badge: the real protocol client runs
against a fake deck, and every TCP connection the integration opens during
the config flow, setup, polling and commands is recorded. All of them must
go to the host and port entered in the config flow. Real network access is
blocked in the tests anyway, so anything else would fail. The static half
is scripts/check_local_only.py, which is tested here as well.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any
from unittest.mock import patch

from custom_components.blackmagic_hyperdeck.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import HOST, PORT, USER_INPUT

ROOT = Path(__file__).resolve().parents[1]

_BANNER = (
    b"500 connection info:\r\n"
    b"protocol version: 1.8\r\n"
    b"model: HyperDeck Studio Pro\r\n"
    b"\r\n"
)
_ANSWERS: dict[str, bytes] = {
    "transport info": (
        b"208 transport info:\r\n"
        b"status: play\r\n"
        b"speed: 100\r\n"
        b"slot id: 1\r\n"
        b"clip id: 1\r\n"
        b"single clip: false\r\n"
        b"loop: false\r\n"
        b"video format: 1080p25\r\n"
        b"timecode: 00:00:10:00\r\n"
        b"\r\n"
    ),
    "slot info": b"202 slot info:\r\nslot id: 1\r\nstatus: mounted\r\n\r\n",
    "configuration": b"211 configuration:\r\nvideo input: SDI\r\n\r\n",
    "clips get": (
        b"205 clips info:\r\n"
        b"clip count: 1\r\n"
        b"1: Show open.mov 00:00:00:00 00:01:00:00\r\n"
        b"\r\n"
    ),
}


class _FakeDeck:
    """One TCP connection to a fake HyperDeck: a stream reader plus a writer.

    It sends the connection banner, answers status queries with a block and
    every other command with "200 ok", and remembers each command it got.
    """

    def __init__(self) -> None:
        self.reader = asyncio.StreamReader()
        self.reader.feed_data(_BANNER)
        self.commands: list[str] = []

    def write(self, data: bytes) -> None:
        for line in data.decode("utf-8").split("\r\n"):
            if line:
                self.commands.append(line)
                self.reader.feed_data(_ANSWERS.get(line, b"200 ok\r\n"))

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.reader.feed_eof()

    async def wait_closed(self) -> None:
        return None


def _load_checker() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_local_only", ROOT / "scripts" / "check_local_only.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    if entity_id is None:
        raise AssertionError(f"No {platform} entity with unique_id {unique_id}")
    return entity_id


async def test_all_traffic_goes_to_the_deck(hass: HomeAssistant) -> None:
    """Config flow, setup, polling and commands only reach the configured deck."""
    opened: list[tuple[str, int]] = []
    decks: list[_FakeDeck] = []

    async def _open_connection(host: str, port: int, *args: Any, **kwargs: Any) -> Any:
        opened.append((host, port))
        deck = _FakeDeck()
        decks.append(deck)
        return deck.reader, deck

    with (
        patch.object(asyncio, "open_connection", _open_connection),
        patch("custom_components.blackmagic_hyperdeck.coordinator.POLL_INTERVAL", 0.01),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        # Let the background loop poll the deck a few times.
        await asyncio.sleep(0.1)

        entry_id = entry.entry_id
        player_id = _entity_id(hass, "media_player", f"{entry_id}_media_player")
        for service, data in (
            ("media_play", {}),
            ("media_pause", {}),
            ("media_stop", {}),
            ("media_next_track", {}),
            ("media_seek", {"seek_position": 5}),
        ):
            await hass.services.async_call(
                "media_player", service, {"entity_id": player_id, **data}, blocking=True
            )
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": _entity_id(hass, "button", f"{entry_id}_record")},
            blocking=True,
        )
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": _entity_id(hass, "switch", f"{entry_id}_loop")},
            blocking=True,
        )

        assert await hass.config_entries.async_unload(entry_id)
        await hass.async_block_till_done()

    sent = [command for deck in decks for command in deck.commands]
    assert len(opened) >= 2, "expected a connection from the config flow and from setup"
    assert set(opened) == {(HOST, PORT)}
    for expected in ("transport info", "clips get", "stop", "record", "goto: clip id: +1"):
        assert expected in sent, expected
    assert any(command.startswith("goto: timecode: ") for command in sent)


def test_static_check_passes() -> None:
    """The integration passes scripts/check_local_only.py."""
    checker = _load_checker()
    assert checker.main(["check_local_only.py"]) == 0


def test_static_check_catches_leaks(tmp_path: Path) -> None:
    """The check fails on an integration that could send data elsewhere."""
    checker = _load_checker()
    leaky = tmp_path / "leaky"
    shutil.copytree(ROOT / "custom_components" / "blackmagic_hyperdeck", leaky)
    manifest = json.loads((leaky / "manifest.json").read_text())
    manifest.update(iot_class="cloud_polling", requirements=["phonehome==1.0"])
    (leaky / "manifest.json").write_text(json.dumps(manifest))
    (leaky / "telemetry.py").write_text(
        "import asyncio\n"
        "import aiohttp\n"
        "import requests\n"
        "from homeassistant.helpers.aiohttp_client import async_get_clientsession\n\n\n"
        "async def leak(hass):\n"
        "    session = async_get_clientsession(hass)\n"
        "    await session.post('https://telemetry.example.com/collect')\n"
        "    await asyncio.start_server(None, '0.0.0.0', 8080)\n"
        "    await asyncio.open_connection('8.8.8.8', 53)\n"
        "    return 'analytics.vendor.io'\n"
    )

    problems = checker.check_manifest(leaky)
    problems += checker.check_source(leaky / "telemetry.py", "leaky/telemetry.py")
    text = "\n".join(problems)
    for expected in (
        "iot_class",
        "phonehome",
        "imports aiohttp",
        "imports requests",
        "imports homeassistant.helpers.aiohttp_client",
        "async_get_clientsession() outside",
        "session.post() outside",
        "start_server() listens",
        "open_connection() outside",
        "https://telemetry.example.com",
        "8.8.8.8",
        "analytics.vendor.io",
    ):
        assert expected in text, expected
    assert checker.main(["check_local_only.py", str(leaky)]) == 1
