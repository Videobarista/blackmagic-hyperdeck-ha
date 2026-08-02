"""Coordinator for the Blackmagic HyperDeck integration.

Uses the notification websocket for realtime push updates, with REST polling
as fallback (and for values not worth subscribing to, like timecode).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import HyperDeckClient, HyperDeckConnectionError, HyperDeckError
from .const import CLIPS_REFRESH_EVERY, DEFAULT_SCAN_INTERVAL, DOMAIN, WS_PROPERTIES

_LOGGER = logging.getLogger(__name__)

# Map websocket property -> key in coordinator data
_WS_KEY_MAP = {
    "/transports/0": "transport",
    "/transports/0/playback": "playback",
    "/transports/0/record": "record",
    "/transports/0/clipIndex": "clip_index",
    "/timelines/0": "timeline",
}


class HyperDeckCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds HyperDeck state and pushes websocket updates to entities."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HyperDeckClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.host}",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.position_updated_at = dt_util.utcnow()
        self._ws_task: asyncio.Task | None = None
        self._poll_count = 0

    # ----------------------------------------------------------------- poll
    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(self.data or {})
        try:
            (
                transport,
                playback,
                record,
                timecode,
                clip_index,
                clip,
                timeline,
            ) = await asyncio.gather(
                self.client.get_transport(),
                self.client.get_playback(),
                self.client.get_record(),
                self.client.get_timecode(),
                self.client.get_clip_index(),
                self.client.get_current_clip(),
                self.client.get_timeline(),
            )
            if data.get("system") is None:
                data["system"] = await self.client.get_system()
            if data.get("product") is None:
                data["product"] = await self.client.get_product()
            if data.get("clips") is None or self._poll_count % CLIPS_REFRESH_EVERY == 0:
                data["clips"] = await self.client.get_clips()
        except HyperDeckConnectionError as err:
            raise UpdateFailed(str(err)) from err
        except HyperDeckError as err:
            raise UpdateFailed(f"HyperDeck API error: {err}") from err

        self._poll_count += 1
        data.update(
            {
                "transport": transport,
                "playback": playback,
                "record": record,
                "timecode": timecode,
                "clip_index": clip_index,
                "clip": clip,
                "timeline": timeline,
            }
        )
        self.position_updated_at = dt_util.utcnow()
        return data

    # ------------------------------------------------------------ websocket
    def start_websocket(self) -> None:
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = self.config_entry.async_create_background_task(
                self.hass, self._ws_loop(), name=f"{DOMAIN}_ws_{self.client.host}"
            )

    async def stop_websocket(self) -> None:
        if self._ws_task is not None:
            self._ws_task.cancel()
            self._ws_task = None

    async def _ws_loop(self) -> None:
        while True:
            try:
                await self.client.listen(WS_PROPERTIES, self._on_ws_property)
                _LOGGER.debug("HyperDeck websocket closed, reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - keep the loop alive
                _LOGGER.debug("HyperDeck websocket error: %s", err)
            await asyncio.sleep(10)

    def _on_ws_property(self, prop: str, value: Any) -> None:
        """Handle a pushed property change (runs in the event loop)."""
        key = _WS_KEY_MAP.get(prop)
        if key is None:
            if prop == "/media/active":
                # Disk changed: clip list is stale, refetch on next poll.
                new = dict(self.data or {})
                new["clips"] = None
                self.async_set_updated_data(new)
            return
        new = dict(self.data or {})
        new[key] = value
        if key == "playback":
            self.position_updated_at = dt_util.utcnow()
        self.async_set_updated_data(new)

    # ------------------------------------------------------------- helpers
    @property
    def playback(self) -> dict[str, Any]:
        return (self.data or {}).get("playback") or {}

    @property
    def is_recording(self) -> bool:
        record = (self.data or {}).get("record") or {}
        return bool(record.get("recording"))

    @property
    def timeline_clips(self) -> list[dict[str, Any]]:
        timeline = (self.data or {}).get("timeline") or {}
        return timeline.get("clips") or []

    @property
    def clip_index(self) -> int | None:
        ci = (self.data or {}).get("clip_index") or {}
        idx = ci.get("clipIndex")
        return int(idx) if idx is not None else None

    @property
    def current_clip(self) -> dict[str, Any] | None:
        clip_wrapper = (self.data or {}).get("clip") or {}
        return clip_wrapper.get("clip")

    @property
    def fps(self) -> float:
        """Frame rate of the current clip, falling back to the system format."""
        for source in (self.current_clip, (self.data or {}).get("system")):
            if not source:
                continue
            rate = (source.get("videoFormat") or {}).get("frameRate")
            if rate:
                try:
                    return float(rate)
                except (TypeError, ValueError):
                    continue
        return 25.0

    def clip_name_by_unique_id(self, unique_id: Any) -> str | None:
        clips = ((self.data or {}).get("clips") or {}).get("clips") or []
        for clip in clips:
            if clip.get("clipUniqueId") == unique_id:
                return clip.get("filePath")
        return None

    def timeline_entry(self, index: int | None) -> dict[str, Any] | None:
        clips = self.timeline_clips
        if index is None or not 0 <= index < len(clips):
            return None
        return clips[index]

    @staticmethod
    def _frames(value: Any) -> int:
        """timelineIn/clipIn are documented as strings; parse defensively."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def clip_position_frames(self) -> int | None:
        """Playback position within the current clip, in frames."""
        position = self.playback.get("position")
        if position is None:
            return None
        entry = self.timeline_entry(self.clip_index)
        if entry is None:
            return int(position)
        return max(0, int(position) - self._frames(entry.get("timelineIn")))

    def clip_duration_frames(self) -> int | None:
        entry = self.timeline_entry(self.clip_index)
        if entry is not None and entry.get("frameCount"):
            return int(entry["frameCount"])
        clip = self.current_clip
        if clip is not None and clip.get("frameCount"):
            return int(clip["frameCount"])
        return None

    def clip_progress(self) -> float | None:
        """Progress of the current clip as a percentage (0-100)."""
        pos = self.clip_position_frames()
        dur = self.clip_duration_frames()
        if pos is None or not dur:
            return None
        return round(min(100.0, max(0.0, pos / dur * 100)), 1)

    # ------------------------------------------------------------- actions
    async def async_goto_timeline_clip(self, index: int) -> None:
        entry = self.timeline_entry(index)
        if entry is None:
            return
        await self.client.seek_frames(self._frames(entry.get("timelineIn")))
        await self.async_request_refresh()

    async def async_next_clip(self) -> None:
        idx = self.clip_index
        if idx is not None and idx + 1 < len(self.timeline_clips):
            await self.async_goto_timeline_clip(idx + 1)

    async def async_previous_clip(self) -> None:
        idx = self.clip_index
        if idx is not None and idx > 0:
            await self.async_goto_timeline_clip(idx - 1)

    async def async_restart_clip(self) -> None:
        idx = self.clip_index
        if idx is not None:
            await self.async_goto_timeline_clip(idx)
