"""Constants for the Blackmagic HyperDeck integration."""
from __future__ import annotations

DOMAIN = "blackmagic_hyperdeck"

DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 5  # seconds, polling fallback
CLIPS_REFRESH_EVERY = 12  # refresh the clip list every N polls (~1 min)

CONF_HOST = "host"
CONF_PORT = "port"

MANUFACTURER = "Blackmagic Design"

# Websocket properties we subscribe to. Deliberately NOT /transports/0/timecode:
# the device may push that every frame, which would flood Home Assistant.
WS_PROPERTIES = [
    "/transports/0",
    "/transports/0/playback",
    "/transports/0/record",
    "/transports/0/clipIndex",
    "/timelines/0",
    "/media/active",
]
