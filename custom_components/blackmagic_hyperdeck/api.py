"""Async client for the Blackmagic HyperDeck Ethernet Protocol.

Based on the "HyperDeck Ethernet Protocol" developer documentation
(December 2024). A line-oriented text protocol on TCP port 9993, present
on every network-capable HyperDeck (Studio, Extreme, Shuttle, and their
older siblings). Commands are processed strictly in sequence: the deck
will not answer a second command until it has answered the first, so this
client serialises writes with a lock and a single in-flight response
future.

Two kinds of blocks arrive from the deck:
  * A reply to a command we sent (response codes 100-499).
  * An unsolicited push notification (response codes 500-599), including
    the "connection info" banner sent automatically right after connect,
    and further pushes once notifications are enabled with `notify`.

A block is either a single line (`{code} {text}`) or, when the first line
ends with a colon, a multi-line block of `{key}: {value}` pairs terminated
by a blank line.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .const import COMMAND_TIMEOUT, CONNECT_TIMEOUT, DEFAULT_FPS

_LOGGER = logging.getLogger(__name__)

_TIMECODE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}:\d{2})\s*")
_TRAILING_TIMECODES_RE = re.compile(
    r"\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s*$"
)
_RATE_RE = re.compile(r"([pi])(\d+(?:\.\d+)?)$")

# Every non-drop frame rate documented across HyperDeck's video-format
# names, keyed by the digits Blackmagic uses after "p"/"i" - with or
# without a decimal point, since different format families in Blackmagic's
# own docs are inconsistent about this (e.g. "1080p2997" vs "2160p29.97"
# for the same 29.97fps).
_KNOWN_RATES: dict[str, float] = {
    "23976": 23.976, "23.98": 23.976, "23.976": 23.976,
    "24": 24.0,
    "25": 25.0,
    "2997": 29.97, "29.97": 29.97,
    "30": 30.0,
    "4795": 47.95, "47.95": 47.95,
    "48": 48.0,
    "50": 50.0,
    "5994": 59.94, "59.94": 59.94,
    "60": 60.0,
    "11988": 119.88, "119.88": 119.88,
    "120": 120.0,
}


def parse_video_format_fps(fmt: str | None) -> float:
    """Best-effort frame rate from a HyperDeck video-format name.

    Handles both digit-run styles seen in Blackmagic's own documentation
    ("1080p2997" and "2160p29.97" both mean 29.97fps), the bare NTSC/PAL
    names some models report, and interlace formats - by broadcast
    convention the digits after "i" are the *field* rate (e.g. "1080i50"
    is 50 fields/sec = 25 frames/sec, matching "1080p25"), and non-drop
    timecode counts frames, so those are halved. Falls back to
    DEFAULT_FPS for anything unrecognised rather than raising - this only
    ever affects the timecode-to-seconds math for the progress bar and
    sensors, never the transport commands themselves.
    """
    if not fmt:
        return DEFAULT_FPS
    upper = fmt.strip().upper()
    if upper in ("NTSC", "NTSCP"):
        return 29.97
    if upper in ("PAL", "PALP"):
        return 25.0
    match = _RATE_RE.search(fmt.strip())
    if not match:
        return DEFAULT_FPS
    scan, digits = match.group(1), match.group(2)
    rate = _KNOWN_RATES.get(digits, DEFAULT_FPS)
    return rate / 2 if scan == "i" else rate


class HyperDeckError(Exception):
    """Base error talking to the HyperDeck."""


class HyperDeckConnectionError(HyperDeckError):
    """Could not reach the HyperDeck, or the connection dropped."""


class HyperDeckCommandError(HyperDeckError):
    """The deck understood us but rejected the command (100-199 response)."""

    def __init__(self, code: int, text: str) -> None:
        super().__init__(f"{code} {text}")
        self.code = code
        self.text = text


@dataclass
class HyperDeckResponse:
    """A single parsed block from the deck."""

    code: int
    text: str
    params: dict[str, str] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return 100 <= self.code < 200

    @property
    def is_async(self) -> bool:
        return 500 <= self.code < 600


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().strip('"').lower() == "true"


def _build_command(name: str, params: dict[str, Any] | None = None) -> str:
    """Build a single-line command using the protocol's combination syntax.

    e.g. _build_command("play", {"loop": True, "speed": 100}) ->
    "play: loop: true speed: 100"
    """
    if not params:
        return name
    parts = [f"{name}:"]
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f"{key}: {value}")
    return " ".join(parts)


def parse_timecode_to_frames(timecode: str | None, nominal_fps: int) -> int | None:
    """Parse HH:MM:SS:FF (non-drop-frame) into a frame count."""
    if not timecode:
        return None
    try:
        h, m, s, f = (int(part) for part in timecode.strip().split(":"))
    except (ValueError, AttributeError):
        return None
    return ((h * 3600 + m * 60 + s) * nominal_fps) + f


def frames_to_timecode(frames: int, nominal_fps: int) -> str:
    """Inverse of parse_timecode_to_frames: frame count -> HH:MM:SS:FF."""
    nominal_fps = nominal_fps or 25
    total_seconds, ff = divmod(max(0, int(frames)), nominal_fps)
    hh, remainder = divmod(total_seconds, 3600)
    mm, ss = divmod(remainder, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def parse_clip_line_v2(clip_id: str, rest: str) -> dict[str, Any]:
    """Parse one line of a `clips get: version: 2` response.

    Format: "{Clip ID}: {Clip start timecode} {Duration timecode}
    {inTimecode} {outTimecode} {name}". The name is last specifically so it
    can contain spaces; we identify the four fixed timecodes by pattern
    from the front and treat everything left over as the name.

    Not currently used by default - see get_clips() - since the
    "version: 2" parameter itself isn't recognised on at least one real
    older HyperDeck (protocol version 1.8), where it triggers a syntax
    error. Kept here in case a future version negotiates up to it.
    """
    tokens: list[str] = []
    remaining = rest
    for _ in range(4):
        match = _TIMECODE_RE.match(remaining)
        if not match:
            break
        tokens.append(match.group(1))
        remaining = remaining[match.end():]
    tokens += [None] * (4 - len(tokens))  # type: ignore[list-item]
    start_tc, duration_tc, in_tc, out_tc = tokens
    try:
        clip_id_int = int(clip_id)
    except ValueError:
        clip_id_int = -1
    return {
        "clip_id": clip_id_int,
        "start_timecode": start_tc,
        "duration_timecode": duration_tc,
        "in_timecode": in_tc,
        "out_timecode": out_tc,
        "name": remaining.strip() or None,
    }


def parse_clip_line_v1(clip_id: str, rest: str) -> dict[str, Any]:
    """Parse one line of the default (bare `clips get`) response.

    Format: "{Clip ID}: {Name} {Start timecode} {Duration timecode}". Here
    the name comes *first*, so - unlike v2 - we identify the two fixed
    timecodes by pattern from the *end* of the line and treat everything
    before them as the name. No in/out points in this format.
    """
    match = _TRAILING_TIMECODES_RE.search(rest)
    if match:
        start_tc, duration_tc = match.group(1), match.group(2)
        name = rest[: match.start()].strip()
    else:
        start_tc = duration_tc = None
        name = rest.strip()
    try:
        clip_id_int = int(clip_id)
    except ValueError:
        clip_id_int = -1
    return {
        "clip_id": clip_id_int,
        "start_timecode": start_tc,
        "duration_timecode": duration_tc,
        "in_timecode": None,
        "out_timecode": None,
        "name": name or None,
    }


class HyperDeckClient:
    """Persistent async connection to a HyperDeck's Ethernet Protocol port."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        on_notification: Callable[[HyperDeckResponse], None] | None = None,
        on_disconnected: Callable[[Exception | None], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._on_notification = on_notification
        self._on_disconnected = on_disconnected

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()
        self._pending: asyncio.Future[HyperDeckResponse] | None = None
        self._connected = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    # ------------------------------------------------------------ connect
    async def connect(self, timeout: float = CONNECT_TIMEOUT) -> HyperDeckResponse:
        """Open the TCP connection and wait for the "connection info" banner."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise HyperDeckConnectionError(
                f"Cannot reach HyperDeck at {self.host}:{self.port}: {err}"
            ) from err

        # The banner is itself an async block (code 500), so read it
        # directly rather than through send_command (nothing was sent).
        try:
            banner = await asyncio.wait_for(self._read_block(), timeout=timeout)
        except (OSError, asyncio.TimeoutError, HyperDeckConnectionError) as err:
            await self._close()
            raise HyperDeckConnectionError(
                f"HyperDeck at {self.host}:{self.port} did not answer: {err}"
            ) from err

        self._connected.set()
        _LOGGER.debug("HyperDeck <- %s %s %s (banner)", banner.code, banner.text, banner.params)
        self._reader_task = asyncio.get_event_loop().create_task(self._reader_loop())
        return banner

    async def disconnect(self) -> None:
        await self._close()

    async def _close(self) -> None:
        self._connected.clear()
        if self._reader_task is not None:
            task, self._reader_task = self._reader_task, None
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass
        self._writer = None
        self._reader = None

    # ------------------------------------------------------------ reading
    async def _readline(self) -> str:
        assert self._reader is not None
        raw = await self._reader.readline()
        if not raw:
            _LOGGER.debug("HyperDeck %s:%s closed the connection", self.host, self.port)
            raise HyperDeckConnectionError("Connection closed by HyperDeck")
        return raw.decode("utf-8", errors="replace").rstrip("\r\n")

    async def _read_block(self) -> HyperDeckResponse:
        first = await self._readline()
        code_str, _, rest = first.partition(" ")
        try:
            code = int(code_str)
        except ValueError as err:
            raise HyperDeckConnectionError(f"Malformed response: {first!r}") from err

        params: dict[str, str] = {}
        if rest.endswith(":"):
            text = rest[:-1]
            while True:
                line = await self._readline()
                if not line:
                    break
                key, sep, value = line.partition(":")
                if sep:
                    params[key.strip()] = value.strip()
                else:
                    # Line without "key: value" shape (e.g. a "clips get"
                    # detail line "1: name ..." still matches - "1" is the
                    # key - but guard against genuinely bare lines anyway).
                    params[line.strip()] = ""
        else:
            text = rest
        return HyperDeckResponse(code=code, text=text, params=params)

    async def _reader_loop(self) -> None:
        try:
            while True:
                block = await self._read_block()
                _LOGGER.debug("HyperDeck <- %s %s %s", block.code, block.text, block.params)
                if block.is_async:
                    if self._on_notification is not None:
                        try:
                            self._on_notification(block)
                        except Exception:  # noqa: BLE001 - never kill the reader
                            _LOGGER.exception("Error handling HyperDeck notification")
                    continue
                if self._pending is not None and not self._pending.done():
                    if block.is_error:
                        self._pending.set_exception(
                            HyperDeckCommandError(block.code, block.text)
                        )
                    else:
                        self._pending.set_result(block)
                    self._pending = None
                else:
                    _LOGGER.debug("Unmatched HyperDeck response: %s", block)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            if self._pending is not None and not self._pending.done():
                self._pending.set_exception(
                    HyperDeckConnectionError(f"Connection lost: {err}")
                )
            self._connected.clear()
            if self._on_disconnected is not None:
                self._on_disconnected(err)

    # --------------------------------------------------------- send/recv
    async def send_command(
        self, command: str, timeout: float = COMMAND_TIMEOUT
    ) -> HyperDeckResponse:
        if not self.connected or self._writer is None:
            raise HyperDeckConnectionError("Not connected to HyperDeck")

        async with self._send_lock:
            loop = asyncio.get_event_loop()
            self._pending = loop.create_future()
            _LOGGER.debug("HyperDeck -> %s", command)
            try:
                self._writer.write((command + "\r\n").encode("utf-8"))
                await self._writer.drain()
            except OSError as err:
                self._pending = None
                raise HyperDeckConnectionError(f"Send failed: {err}") from err

            try:
                return await asyncio.wait_for(self._pending, timeout=timeout)
            except asyncio.TimeoutError as err:
                self._pending = None
                raise HyperDeckConnectionError(
                    f"No response to {command.split(':')[0]!r} within {timeout}s"
                ) from err

    # ------------------------------------------------------------- system
    async def get_device_info(self) -> dict[str, str]:
        resp = await self.send_command("device info")
        return resp.params

    async def get_transport_info(self) -> dict[str, str]:
        resp = await self.send_command("transport info")
        return resp.params

    async def get_slot_info(self) -> dict[str, str]:
        resp = await self.send_command("slot info")
        return resp.params

    async def get_configuration(self) -> dict[str, str]:
        resp = await self.send_command("configuration")
        return resp.params

    async def get_clips(self) -> list[dict[str, Any]]:
        """Fetch the timeline clip list.

        Deliberately sends the bare `clips get` (default/v1 response
        format) rather than `clips get: version: 2`: on real older
        hardware (protocol version 1.8), the "version" parameter itself
        isn't recognised and produces a syntax error. v1's format puts the
        clip name first instead of last, which is harder to parse
        unambiguously when a name contains spaces (see
        parse_clip_line_v1), but that trade-off is worth it for broad
        compatibility with older decks.
        """
        resp = await self.send_command("clips get")
        clips: list[dict[str, Any]] = []
        for key, rest in resp.params.items():
            if key == "clip count":
                continue
            clips.append(parse_clip_line_v1(key, rest))
        return clips

    async def enable_notifications(self, **flags: bool) -> None:
        """Enable each notification flag with its own command.

        Sent individually rather than combined on one line: the protocol
        doc's own worked examples for `notify` only ever show a single
        parameter at a time (unlike `play`/`configuration`, which get
        explicit multi-parameter combination examples) - and in practice a
        real HyperDeck Studio Pro rejected a combined
        "notify: a: true b: true ..." with a syntax error. A rejected
        individual flag (e.g. a notification category this firmware
        predates) is logged and skipped rather than aborting the whole
        connection.
        """
        for key, value in flags.items():
            try:
                await self.send_command(_build_command("notify", {key: value}))
            except HyperDeckCommandError as err:
                _LOGGER.debug("HyperDeck rejected notify flag %r: %s", key, err)

    async def set_watchdog(self, period: int) -> None:
        await self.send_command(f"watchdog: period: {period}")

    # ---------------------------------------------------------- transport
    async def play(
        self,
        *,
        loop: bool | None = None,
        single_clip: bool | None = None,
        speed: float | None = None,
    ) -> None:
        params: dict[str, Any] = {}
        if loop is not None:
            params["loop"] = loop
        if single_clip is not None:
            params["single clip"] = single_clip
        if speed is not None:
            params["speed"] = int(speed)
        await self.send_command(_build_command("play", params))

    async def stop(self) -> None:
        await self.send_command("stop")

    async def record(self, clip_name: str | None = None) -> None:
        params = {"name": clip_name} if clip_name else None
        await self.send_command(_build_command("record", params))

    async def goto_clip_relative(self, count: int) -> None:
        """Jump forward/back {count} clips; clamps at the first/last clip."""
        sign = "+" if count >= 0 else ""
        await self.send_command(f"goto: clip id: {sign}{count}")

    async def goto_clip_start(self) -> None:
        await self.send_command("goto: clip: start")

    async def goto_clip_id(self, clip_id: int) -> None:
        """Jump to the start of a specific clip, by its (1-based) clip id."""
        await self.send_command(f"goto: clip id: {int(clip_id)}")

    async def goto_clip_frame(self, frame: int, nominal_fps: int) -> None:
        """Seek to a frame position within the current clip via 'goto: clip:'.

        Not currently used - see goto_timecode() and the coordinator's
        seek_target_timecode(). On a real older HyperDeck (protocol 1.8),
        "goto: clip: {n}" is rejected as "invalid value" both as a plain
        integer AND as a timecode string, while "goto: clip: start" (the
        keyword form) works fine. Since both value shapes failed for this
        specific sub-command, the "goto: timecode:" command (a different
        sub-command entirely, timeline-absolute rather than clip-relative)
        is worth trying instead - kept here in case a future device turns
        out to support this form after all.
        """
        timecode = frames_to_timecode(frame, nominal_fps)
        await self.send_command(f"goto: clip: {timecode}")

    async def goto_timecode(self, timecode: str) -> None:
        """Seek to an absolute timecode position on the timeline."""
        await self.send_command(f"goto: timecode: {timecode}")
