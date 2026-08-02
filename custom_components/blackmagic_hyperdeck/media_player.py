"""Media player entity for the Blackmagic HyperDeck."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HyperDeckConfigEntry
from .coordinator import HyperDeckCoordinator
from .entity import HyperDeckEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperDeckConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([HyperDeckMediaPlayer(entry.runtime_data)])


class HyperDeckMediaPlayer(HyperDeckEntity, MediaPlayerEntity):
    """The HyperDeck as a media player."""

    _attr_name = None  # use the device name
    _attr_media_content_type = MediaType.MOVIE
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.REPEAT_SET
    )

    def __init__(self, coordinator: HyperDeckCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_media_player"

    # -------------------------------------------------------------- state
    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data or {}
        mode = (data.get("transport") or {}).get("mode")
        if mode == "InputRecord":
            # media_player has no recording state; expose via attributes too.
            return MediaPlayerState.ON
        if mode == "Output":
            speed = self.coordinator.playback.get("speed") or 0
            return MediaPlayerState.PLAYING if speed else MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        return {
            "recording": c.is_recording,
            "transport_mode": ((c.data or {}).get("transport") or {}).get("mode"),
            "timecode": ((c.data or {}).get("timecode") or {}).get("display"),
            "clip_index": c.clip_index,
            "playback_speed": c.playback.get("speed"),
            "clip_progress": c.clip_progress(),
        }

    # ----------------------------------------------------- position/media
    @property
    def media_title(self) -> str | None:
        clip = self.coordinator.current_clip
        if clip is not None:
            return clip.get("filePath")
        entry = self.coordinator.timeline_entry(self.coordinator.clip_index)
        if entry is not None:
            return self.coordinator.clip_name_by_unique_id(entry.get("clipUniqueId"))
        return None

    @property
    def media_duration(self) -> int | None:
        frames = self.coordinator.clip_duration_frames()
        if frames is None:
            return None
        return int(frames / self.coordinator.fps)

    @property
    def media_position(self) -> int | None:
        frames = self.coordinator.clip_position_frames()
        if frames is None:
            return None
        return int(frames / self.coordinator.fps)

    @property
    def media_position_updated_at(self) -> datetime | None:
        return self.coordinator.position_updated_at

    # -------------------------------------------------------------- source
    @property
    def source_list(self) -> list[str] | None:
        names = []
        for entry in self.coordinator.timeline_clips:
            name = self.coordinator.clip_name_by_unique_id(entry.get("clipUniqueId"))
            names.append(name or f"Clip {len(names) + 1}")
        return names or None

    @property
    def source(self) -> str | None:
        entry = self.coordinator.timeline_entry(self.coordinator.clip_index)
        if entry is None:
            return None
        return self.coordinator.clip_name_by_unique_id(entry.get("clipUniqueId"))

    async def async_select_source(self, source: str) -> None:
        sources = self.source_list or []
        if source in sources:
            await self.coordinator.async_goto_timeline_clip(sources.index(source))

    # -------------------------------------------------------------- repeat
    @property
    def repeat(self) -> RepeatMode:
        playback = self.coordinator.playback
        if playback.get("singleClip"):
            return RepeatMode.ONE
        if playback.get("loop"):
            return RepeatMode.ALL
        return RepeatMode.OFF

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        await self.coordinator.client.set_playback(
            loop=repeat in (RepeatMode.ALL, RepeatMode.ONE),
            singleClip=repeat == RepeatMode.ONE,
        )
        await self.coordinator.async_request_refresh()

    # ------------------------------------------------------------ commands
    async def async_media_play(self) -> None:
        await self.coordinator.client.play()
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        await self.coordinator.client.set_playback(speed=0)
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        await self.coordinator.client.stop()
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        await self.coordinator.async_next_clip()

    async def async_media_previous_track(self) -> None:
        await self.coordinator.async_previous_clip()

    async def async_media_seek(self, position: float) -> None:
        c = self.coordinator
        offset = 0
        entry = c.timeline_entry(c.clip_index)
        if entry is not None:
            offset = c._frames(entry.get("timelineIn"))  # noqa: SLF001
        await c.client.seek_frames(offset + int(position * c.fps))
        await c.async_request_refresh()
