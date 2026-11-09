"""Tests for the security guards in the HyperDeck protocol client."""

import asyncio

import pytest

from custom_components.blackmagic_hyperdeck import api


class _FakeWriter:
    """Collects written bytes instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


@pytest.mark.parametrize(
    "command",
    ["play\r\nrecord", "record: name: clip\nstop", "goto: clip id: 1\x00", "stop\r"],
)
async def test_command_with_control_characters_is_refused(command: str) -> None:
    """A CR/LF or other control character never reaches the deck."""
    client = api.HyperDeckClient("10.0.0.50", 9993)
    writer = _FakeWriter()
    client._writer = writer
    client._connected.set()

    with pytest.raises(api.HyperDeckInvalidCommandError):
        await client.send_command(command)
    assert writer.sent == []


async def test_record_name_cannot_inject_a_second_command() -> None:
    """A clip name with a line break is refused as a whole."""
    client = api.HyperDeckClient("10.0.0.50", 9993)
    writer = _FakeWriter()
    client._writer = writer
    client._connected.set()

    with pytest.raises(api.HyperDeckInvalidCommandError):
        await client.record("take 1\r\nstop")
    assert writer.sent == []


def test_redact_hides_identifiers_but_keeps_clip_data() -> None:
    """Serial numbers and disk names are redacted; other values stay."""
    redacted = api.redact(
        {
            "device serial": "S75CNX0W000000R",
            "volume name": "Client project",
            "status": "mounted",
            "1": "Show open.mov 00:00:00:00 00:01:00:00",
        }
    )
    assert redacted["device serial"] == "***"
    assert redacted["volume name"] == "***"
    assert redacted["status"] == "mounted"
    assert redacted["1"] == "Show open.mov 00:00:00:00 00:01:00:00"


def test_sanitize_label() -> None:
    """Device strings lose control characters and are length-capped."""
    assert api.sanitize_label("HyperDeck\r\nStudio\x00 Pro") == "HyperDeckStudio Pro"
    assert len(api.sanitize_label("x" * 500)) == 64
    assert api.sanitize_label(None) == ""


async def test_block_with_too_many_lines_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """An endless response from a misbehaving deck cannot grow memory freely."""
    monkeypatch.setattr(api, "MAX_BLOCK_LINES", 5)
    client = api.HyperDeckClient("10.0.0.50", 9993)
    reader = asyncio.StreamReader()
    client._reader = reader
    reader.feed_data(b"205 clips info:\r\n" + b"key: value\r\n" * 6 + b"\r\n")

    with pytest.raises(api.HyperDeckConnectionError):
        await client._read_block()


async def test_overlong_line_is_treated_as_connection_error() -> None:
    """A line beyond the stream limit becomes a connection error, not a crash."""
    client = api.HyperDeckClient("10.0.0.50", 9993)
    reader = asyncio.StreamReader(limit=1024)
    client._reader = reader
    reader.feed_data(b"500 " + b"x" * 4096 + b"\r\n")

    with pytest.raises(api.HyperDeckConnectionError):
        await client._read_block()
