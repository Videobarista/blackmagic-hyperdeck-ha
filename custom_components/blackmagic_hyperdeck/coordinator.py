"""Coordinator for the Blackmagic HyperDeck integration.

Unlike the REST-based v0.1.0, there is a single persistent TCP connection
per deck (the Ethernet Protocol is stateful and processes commands
strictly in sequence). This coordinator owns that connection's entire
lifecycle - connect, enable notifications, a light poll loop for values
that don't get pushed (mainly timecode), and reconnect-with-backoff if the
socket drops - in one background task, and feeds updates to entities via
the normal DataUpdateCoordinator listener mechanism. HA's own polling
scheduler is not used (`update_interval` is left unset); every update is
pushed in explicitly via `async_set_updated_data`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import (
    HyperDeckClient,
    HyperDeckConnectionError,
    HyperDeckError,
    HyperDeckResponse,
    parse_timecode_to_frames,
    parse_video_format_fps,
)
from .const import (
    CLIPS_REFRESH_EVERY,
    DEFAULT_FPS,
    DOMAIN,
    NOMINAL_FPS,
    POLL_INTERVAL,
    RECONNECT_DELAY,
    WATCHDOG_PERIOD,
)

_LOGGER = logging.getLogger(__name__)


def _bool(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


class HyperDeckCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns the connection and holds the latest known HyperDeck state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, host: str, port: int) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{host}", config_entry=entry)
        self.client = HyperDeckClient(
            host,
            port,
            on_notification=self._on_notification,
            on_disconnected=self._on_disconnected,
        )
        self.position_updated_at = dt_util.utcnow()
        self._run_task: asyncio.Task | None = None
        self._poll_count = 0

    # ------------------------------------------------------------- start
    def start(self) -> None:
        if self._run_task is None or self._run_task.done():
            self._run_task = self.config_entry.async_create_background_task(
                self.hass, self._run(), name=f"{DOMAIN}_connection_{self.client.host}"
            )

    async def stop(self) -> None:
        if self._run_task is not None:
            self._run_task.cancel()
            self._run_task = None
        await self.client.disconnect()

    async def async_setup(self) -> None:
        """Connect and fetch once synchronously, then start the background loop.

        Deliberately not named/wired as `async_config_entry_first_refresh`
        (the DataUpdateCoordinator base class method) since this doesn't
        go through `_async_update_data` - raises the api.py exceptions
        directly so `__init__.py` can turn them into `ConfigEntryNotReady`.
        """
        await self._connect_and_sync()
        self.start()

    # --------------------------------------------------------- main loop
    async def _run(self) -> None:
        first = True
        while True:
            try:
                if not first:
                    await self._connect_and_sync()
                first = False
                await self._poll_loop()
            except asyncio.CancelledError:
                raise
            except HyperDeckConnectionError as err:
                _LOGGER.debug("HyperDeck connection lost/unavailable: %s", err)
            except Exception:  # noqa: BLE001 - keep the loop alive regardless
                _LOGGER.exception("Unexpected error in HyperDeck connection loop")
            self.last_update_success = False
            self.async_update_listeners()
            await self.client.disconnect()
            await asyncio.sleep(RECONNECT_DELAY)

    async def _poll_loop(self) -> None:
        while self.client.connected:
            await asyncio.sleep(POLL_INTERVAL)
            transport = await self.client.get_transport_info()
            self._merge({"transport": transport})
            self.position_updated_at = dt_util.utcnow()
            self._poll_count += 1
            if self._poll_count % CLIPS_REFRESH_EVERY == 0:
                await self._refresh_clips()

    # ------------------------------------------------------ connect/sync
    async def _connect_and_sync(self) -> None:
        await self.client.connect()
        try:
            # "clips"/"disk" deliberately omitted: on a real HyperDeck
            # Studio Pro, both are rejected with a syntax error - likely a
            # newer protocol addition this older firmware predates - and
            # the deck then drops the TCP connection outright shortly
            # after, so tolerating the error response isn't sufficient
            # protection. The clip list is refreshed via the periodic poll
            # instead (see CLIPS_REFRESH_EVERY), just less instantly.
            await self.client.enable_notifications(
                transport=True, slot=True, configuration=True
            )
            await self.client.set_watchdog(WATCHDOG_PERIOD)
            device = await self.client.get_device_info()
            transport = await self.client.get_transport_info()
            slot = await self.client.get_slot_info()
            configuration = await self.client.get_configuration()
            clips = await self.client.get_clips()
        except HyperDeckError:
            await self.client.disconnect()
            raise
        self.async_set_updated_data(
            {
                "device": device,
                "transport": transport,
                "slot": slot,
                "configuration": configuration,
                "clips": clips,
            }
        )
        self.position_updated_at = dt_util.utcnow()
        self._poll_count = 0

    async def async_refresh_transport(self) -> None:
        """Re-fetch transport info right away after we issue a command.

        Entities call this instead of the base class's
        `async_request_refresh()` - that goes through `_async_update_data`,
        which this coordinator never overrides, since state normally
        arrives via the connection loop's own poll/push handling instead.
        A push notification confirming our own command usually arrives
        anyway; this just avoids waiting up to POLL_INTERVAL for it.
        """
        if not self.client.connected:
            return
        try:
            transport = await self.client.get_transport_info()
        except HyperDeckError:
            return
        self._merge({"transport": transport})
        self.position_updated_at = dt_util.utcnow()

    async def _refresh_clips(self) -> None:
        try:
            clips = await self.client.get_clips()
        except HyperDeckError:
            return
        self._merge({"clips": clips})

    def _merge(self, patch: dict[str, Any]) -> None:
        new = dict(self.data or {})
        new.update(patch)
        self.async_set_updated_data(new)

    # ------------------------------------------------------- notifications
    def _on_notification(self, block: HyperDeckResponse) -> None:
        """Handle an unsolicited push from the deck (runs on the event loop)."""
        if block.text == "transport info":
            self._merge({"transport": block.params})
            self.position_updated_at = dt_util.utcnow()
        elif block.text == "slot info":
            self._merge({"slot": block.params})
        elif block.text == "configuration":
            # Not exposed as its own entity, but "timecode output" here is
            # what clip_position_frames() needs to interpret "timecode"
            # unambiguously - see that method's docstring.
            self._merge({"configuration": block.params})
        elif block.text in ("clips info", "disk list"):
            # A partial "add" or full "snapshot" update; simplest and most
            # robust is to just refetch the authoritative list.
            self.hass.async_create_task(self._refresh_clips())
        # "remote info" / "connection info" pushes aren't currently
        # surfaced anywhere; ignored deliberately.

    def _on_disconnected(self, err: Exception | None) -> None:
        _LOGGER.debug("HyperDeck %s disconnected: %s", self.client.host, err)
        self.last_update_success = False
        self.async_update_listeners()

    # ------------------------------------------------------------- helpers
    @property
    def transport(self) -> dict[str, str]:
        return (self.data or {}).get("transport") or {}

    @property
    def device(self) -> dict[str, str]:
        return (self.data or {}).get("device") or {}

    @property
    def status(self) -> str | None:
        return self.transport.get("status")

    @property
    def is_recording(self) -> bool:
        return self.status == "record"

    @property
    def loop(self) -> bool:
        return _bool(self.transport.get("loop"))

    @property
    def single_clip(self) -> bool:
        return _bool(self.transport.get("single clip"))

    @property
    def speed(self) -> float:
        try:
            return float(self.transport.get("speed") or 0)
        except ValueError:
            return 0.0

    @property
    def fps(self) -> float:
        return parse_video_format_fps(self.transport.get("video format"))

    @property
    def nominal_fps(self) -> int:
        fps = self.fps
        return NOMINAL_FPS.get(fps, round(fps) or int(DEFAULT_FPS))

    @property
    def current_clip_id(self) -> int | None:
        raw = self.transport.get("clip id")
        if not raw or raw == "none":
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def clip_by_id(self, clip_id: int | None) -> dict[str, Any] | None:
        if clip_id is None:
            return None
        for clip in (self.data or {}).get("clips") or []:
            if clip.get("clip_id") == clip_id:
                return clip
        return None

    @property
    def current_clip(self) -> dict[str, Any] | None:
        return self.clip_by_id(self.current_clip_id)

    @property
    def clips(self) -> list[dict[str, Any]]:
        return (self.data or {}).get("clips") or []

    def clip_duration_frames(self, clip: dict[str, Any] | None = None) -> int | None:
        clip = clip if clip is not None else self.current_clip
        if clip is None:
            return None
        return parse_timecode_to_frames(clip.get("duration_timecode"), self.nominal_fps)

    @property
    def timecode_output(self) -> str | None:
        """The deck's own (read-only, never written by this integration)
        "configuration: timecode output" setting - "clip" or "timeline".
        Determines how to interpret "transport info"'s "timecode" field.
        """
        return ((self.data or {}).get("configuration") or {}).get("timecode output")

    def clip_position_frames(self) -> int | None:
        """Playback position within the current clip, in frames.

        "transport info"'s "timecode" is timeline-relative or clip-relative
        depending on the deck's own "configuration: timecode output"
        setting. This integration deliberately never *changes* that
        setting itself - it can affect what's shown on the deck's own
        front-panel display, which matters for a device used live during a
        show - but it does read it once at connect (and keep it fresh via
        the "configuration" push notification) specifically so this
        calculation doesn't have to guess: a value can legitimately fall
        within a clip's own duration whether it's already clip-relative or
        just happens to be timeline-relative and early in a long clip, so
        range-checking alone can't tell those apart.
        """
        tc_frames = parse_timecode_to_frames(self.transport.get("timecode"), self.nominal_fps)
        if tc_frames is None:
            return None
        clip = self.current_clip
        duration = self.clip_duration_frames(clip)

        if self.timecode_output == "timeline" and clip is not None:
            start_frames = parse_timecode_to_frames(clip.get("start_timecode"), self.nominal_fps)
            if start_frames is not None:
                relative = tc_frames - start_frames
                if duration:
                    relative = max(0, min(relative, duration))
                return max(0, relative)

        # "clip" mode, or setting not known yet: treat as clip-relative
        # already, clamping defensively in case it isn't.
        if duration:
            return max(0, min(tc_frames, duration))
        return tc_frames

    def clip_progress(self) -> float | None:
        """Progress of the current clip as a percentage (0-100)."""
        pos = self.clip_position_frames()
        dur = self.clip_duration_frames()
        if pos is None or not dur:
            return None
        return round(min(100.0, max(0.0, pos / dur * 100)), 1)

    # ------------------------------------------------------------- actions
    async def async_next_clip(self) -> None:
        await self.client.goto_clip_relative(1)

    async def async_previous_clip(self) -> None:
        await self.client.goto_clip_relative(-1)

    async def async_restart_clip(self) -> None:
        await self.client.goto_clip_start()
