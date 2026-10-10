"""Tests for the Teranex protocol parser, independent of Home Assistant."""

from __future__ import annotations

import asyncio
import logging

import pytest

from custom_components.blackmagic_teranex.protocol import TeranexClient

DUMP = """PROTOCOL PREAMBLE:
Version: 1.13

TERANEX DEVICE:
Model name: Teranex 2D
Software Version: 0x74e4b2e

ANCILLARY DATA:
Timecode generate value: 00:00:00;00

VIDEO OUTPUT:
Video mode: 1080p24
Aspect ratio: Anamorphic

"""


def _feed(client: TeranexClient, text: str) -> None:
    for line in text.split("\n"):
        client._handle_line(line)


async def test_dump_is_parsed_into_blocks() -> None:
    """Blocks and values arrive exactly as the unit spells them."""
    client = TeranexClient("unit")
    _feed(client, DUMP)

    assert client.model == "Teranex 2D"
    assert client.get("VIDEO OUTPUT", "Video mode") == "1080p24"
    # Only the first colon separates key and value.
    assert client.get("ANCILLARY DATA", "Timecode generate value") == "00:00:00;00"
    assert client.get("VIDEO OUTPUT", "Missing") is None


async def test_partial_update_is_merged() -> None:
    """A status update carries only what changed and keeps the rest."""
    client = TeranexClient("unit")
    _feed(client, DUMP)
    _feed(client, "VIDEO OUTPUT:\nAspect ratio: CentreCut\n\n")

    assert client.get("VIDEO OUTPUT", "Aspect ratio") == "CentreCut"
    assert client.get("VIDEO OUTPUT", "Video mode") == "1080p24"


async def test_listeners_fire_per_block() -> None:
    """Every completed block notifies the listeners once."""
    client = TeranexClient("unit")
    calls: list[int] = []
    remove = client.add_listener(lambda: calls.append(1))

    _feed(client, DUMP)
    assert len(calls) == 4

    remove()
    _feed(client, "VIDEO OUTPUT:\nAspect ratio: Letterbox\n\n")
    assert len(calls) == 4


async def test_ack_and_nack_resolve_waiters_in_order() -> None:
    """Replies are matched to commands in the order they were sent."""
    client = TeranexClient("unit")
    loop = asyncio.get_running_loop()
    first: asyncio.Future[bool] = loop.create_future()
    second: asyncio.Future[bool] = loop.create_future()
    client._waiters.extend([first, second])

    _feed(client, "ACK\n\nNACK\n\n")

    assert first.result() is True
    assert second.result() is False


async def test_wait_ready_times_out_without_device() -> None:
    """Waiting for an unreachable unit returns instead of raising."""
    client = TeranexClient("unit")
    assert await client.async_wait_ready(0.01) is False

    _feed(client, DUMP)
    assert await client.async_wait_ready(0.01) is True


@pytest.mark.parametrize("sequence", [[False, False, True, True, False]])
async def test_reachability_logged_once_per_change(
    caplog: pytest.LogCaptureFixture, sequence: list[bool]
) -> None:
    """Retries while a unit stays off do not fill the log."""
    client = TeranexClient("unit")
    with caplog.at_level(logging.INFO):
        for online in sequence:
            client._log_reachability(online)

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "Teranex unit:9800 is offline, will keep trying to reconnect",
        "Teranex unit:9800 is online",
        "Teranex unit:9800 is offline, will keep trying to reconnect",
    ]
