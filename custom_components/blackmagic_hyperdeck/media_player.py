"""Media player entity for the Blackmagic HyperDeck."""
from __future__ import annotations

from datetime import datetime
from typing import Any

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

# Deck transport "status" values that represent some form of active
# playback (as opposed to fully stopped/idle or recording).
_PLAYING_STATUSES = {"play", "forward", "rewind", "jog", "shuttle"}


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
        c = self.coordinator
        if c.is_recording:
            # media_player has no dedicated recording state; the "record"
            # sensor/attribute below carries the detail.
            return MediaPlayerState.ON
        if c.status in _PLAYING_STATUSES:
            return MediaPlayerState.PLAYING if c.speed else MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        return {
            "recording": c.is_recording,
            "transport_status": c.status,
            "timecode": c.transport.get("display timecode") or c.transport.get("timecode"),
            "clip_id": c.current_clip_id,
            "playback_speed": c.speed,
            "clip_progress": c.clip_progress(),
        }

    # ----------------------------------------------------- position/media
    @property
    def media_title(self) -> str | None:
        clip = self.coordinator.current_clip
        return clip.get("name") if clip else None

    @property
    def media_duration(self) -> int | None:
        frames = self.coordinator.clip_duration_frames()
        if frames is None:
            return None
        return round(frames / self.coordinator.fps)

    @property
    def media_position(self) -> int | None:
        frames = self.coordinator.clip_position_frames()
        if frames is None:
            return None
        return round(frames / self.coordinator.fps)

    @property
    def media_position_updated_at(self) -> datetime | None:
        return self.coordinator.position_updated_at

    # -------------------------------------------------------------- source
    @property
    def source_list(self) -> list[str] | None:
        names = [clip.get("name") or f"Clip {clip['clip_id']}" for clip in self.coordinator.clips]
        return names or None

    @property
    def source(self) -> str | None:
        clip = self.coordinator.current_clip
        return clip.get("name") if clip else None

    async def async_select_source(self, source: str) -> None:
        for clip in self.coordinator.clips:
            if (clip.get("name") or f"Clip {clip['clip_id']}") == source:
                await self.coordinator.client.goto_clip_id(clip["clip_id"])
                await self.coordinator.async_refresh_transport()
                break

    # -------------------------------------------------------------- repeat
    @property
    def repeat(self) -> RepeatMode:
        c = self.coordinator
        if c.single_clip:
            return RepeatMode.ONE
        if c.loop:
            return RepeatMode.ALL
        return RepeatMode.OFF

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        # NOTE: the Ethernet Protocol has no standalone "set loop/single
        # clip" command - loop and single-clip are parameters of "play"
        # itself. We pass the deck's current speed straight through
        # (rather than defaulting to some value) so that toggling repeat
        # while stopped doesn't unexpectedly start playback.
        c = self.coordinator
        await c.client.play(
            loop=repeat in (RepeatMode.ALL, RepeatMode.ONE),
            single_clip=repeat == RepeatMode.ONE,
            speed=c.speed,
        )
        await c.async_refresh_transport()

    # ------------------------------------------------------------ commands
    async def async_media_play(self) -> None:
        c = self.coordinator
        await c.client.play(loop=c.loop, single_clip=c.single_clip, speed=100)
        await c.async_refresh_transport()

    async def async_media_pause(self) -> None:
        c = self.coordinator
        await c.client.play(loop=c.loop, single_clip=c.single_clip, speed=0)
        await c.async_refresh_transport()

    async def async_media_stop(self) -> None:
        await self.coordinator.client.stop()
        await self.coordinator.async_refresh_transport()

    async def async_media_next_track(self) -> None:
        await self.coordinator.async_next_clip()
        await self.coordinator.async_refresh_transport()

    async def async_media_previous_track(self) -> None:
        await self.coordinator.async_previous_clip()
        await self.coordinator.async_refresh_transport()

    async def async_media_seek(self, position: float) -> None:
        frame = round(position * self.coordinator.fps)
        await self.coordinator.client.goto_clip_frame(frame)
        await self.coordinator.async_refresh_transport()
