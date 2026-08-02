"""Async client for the Blackmagic HyperDeck Control REST API.

Based on the "REST API for HyperDeck" developer documentation (December 2024).
Covers HyperDeck Extreme, Shuttle and Studio models.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_PREFIX = "/control/api/v1"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class HyperDeckError(Exception):
    """Error talking to the HyperDeck."""


class HyperDeckConnectionError(HyperDeckError):
    """Could not reach the HyperDeck."""


class HyperDeckClient:
    """Minimal async wrapper around the HyperDeck Control REST API."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        self.host = host
        self.port = port
        self._session = session
        self._base = f"http://{host}:{port}{API_PREFIX}"
        self.ws_url = f"ws://{host}:{port}{API_PREFIX}/event/websocket"

    # ------------------------------------------------------------------ http
    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method, url, json=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 204:
                    return None
                if resp.status == 404:
                    # e.g. no active disk / no timeline; treat as "no data"
                    return None
                if resp.status >= 400:
                    raise HyperDeckError(
                        f"{method} {path} failed with HTTP {resp.status}"
                    )
                if "json" in (resp.content_type or ""):
                    return await resp.json()
                text = await resp.text()
                return json.loads(text) if text else None
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HyperDeckConnectionError(
                f"Cannot reach HyperDeck at {self.host}:{self.port}: {err}"
            ) from err

    async def _get(self, path: str) -> Any:
        return await self._request("GET", path)

    # --------------------------------------------------------------- system
    async def get_system(self) -> dict[str, Any] | None:
        return await self._get("/system")

    async def get_product(self) -> dict[str, Any] | None:
        return await self._get("/system/product")

    async def identify(self) -> None:
        await self._request("PUT", "/system/identify")

    # ------------------------------------------------------------ transport
    async def get_transport(self) -> dict[str, Any] | None:
        return await self._get("/transports/0")

    async def get_playback(self) -> dict[str, Any] | None:
        return await self._get("/transports/0/playback")

    async def get_record(self) -> dict[str, Any] | None:
        return await self._get("/transports/0/record")

    async def get_timecode(self) -> dict[str, Any] | None:
        return await self._get("/transports/0/timecode")

    async def get_clip_index(self) -> dict[str, Any] | None:
        return await self._get("/transports/0/clipIndex")

    async def get_current_clip(self) -> dict[str, Any] | None:
        return await self._get("/transports/0/clip")

    async def play(self) -> None:
        await self._request("POST", "/transports/0/play")

    async def stop(self) -> None:
        await self._request("POST", "/transports/0/stop")

    async def record(self, clip_name: str | None = None) -> None:
        payload = {"clipName": clip_name} if clip_name else None
        await self._request("POST", "/transports/0/record", payload)

    async def set_playback(self, **kwargs: Any) -> None:
        """PUT /transports/0/playback — accepts type, loop, singleClip, speed, position."""
        await self._request("PUT", "/transports/0/playback", kwargs)

    async def seek_frames(self, position: int) -> None:
        await self.set_playback(position=int(position))

    # ------------------------------------------------------------- timeline
    async def get_timeline(self) -> dict[str, Any] | None:
        return await self._get("/timelines/0")

    async def get_clips(self) -> dict[str, Any] | None:
        return await self._get("/clips")

    # ------------------------------------------------------------ websocket
    async def listen(
        self,
        properties: list[str],
        callback: Callable[[str, Any], None],
        on_connect: Callable[[], None] | None = None,
    ) -> None:
        """Connect to the notification websocket and dispatch property updates.

        Runs until the connection drops or the task is cancelled.
        """
        async with self._session.ws_connect(self.ws_url, heartbeat=30) as ws:
            await ws.send_json(
                {
                    "type": "request",
                    "id": 1,
                    "data": {"action": "subscribe", "properties": properties},
                }
            )
            if on_connect is not None:
                on_connect()
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        self._dispatch(json.loads(msg.data), callback)
                    except (ValueError, KeyError) as err:
                        _LOGGER.debug("Ignoring malformed ws message: %s", err)
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break

    @staticmethod
    def _dispatch(message: dict[str, Any], callback: Callable[[str, Any], None]) -> None:
        data = message.get("data") or {}
        msg_type = message.get("type")
        if msg_type == "event" and data.get("action") == "propertyValueChanged":
            prop = data.get("property")
            if prop:
                callback(prop, data.get("value"))
        elif msg_type == "response":
            # Subscribe responses carry initial values keyed by property.
            for prop, value in (data.get("values") or {}).items():
                callback(prop, value)
