"""Constants for the Blackmagic HyperDeck integration.

v0.2.0 switches the transport from the December 2024 REST API to the
classic HyperDeck Ethernet Protocol (TCP port 9993). The REST API is only
present on recent firmware for the current Extreme/Shuttle/Studio line;
the Ethernet Protocol has shipped on every network-capable HyperDeck since
roughly 2013 and is still documented alongside REST today, so it is the
broadly-compatible choice for a public HACS integration.
"""
from __future__ import annotations

DOMAIN = "blackmagic_hyperdeck"

DEFAULT_PORT = 9993

# How long we wait for the deck to send its unsolicited "connection info"
# banner right after the TCP handshake completes.
CONNECT_TIMEOUT = 5
# How long we wait for a response to a command we sent.
COMMAND_TIMEOUT = 10
# Delay between reconnect attempts after the connection drops.
RECONNECT_DELAY = 10
# We ask the deck to disconnect us if it hears nothing for this long. Kept
# generous since our own poll loop below will normally keep the line busy
# well within this window anyway.
WATCHDOG_PERIOD = 30
# Light poll of "transport info" between pushes, mainly to keep the
# timecode/progress sensors fresh. We deliberately do NOT subscribe to
# "notify: display timecode" / "notify: timeline position" - those push on
# every frame during playback and would flood the single TCP connection we
# also use for commands.
POLL_INTERVAL = 2
# How often "clips get" is refreshed absent a "clips"/"disk" notification.
CLIPS_REFRESH_EVERY = 15  # ~every 30s at POLL_INTERVAL=2

CONF_HOST = "host"
CONF_PORT = "port"

MANUFACTURER = "Blackmagic Design"

# Nominal (non-drop-frame) frames-per-second used for the FF component of a
# timecode string, keyed by the actual frame rate reported by the deck.
# NTSC-family rates count frames 0..(nominal-1) even though real time runs
# slightly slower than the nominal rate implies - see NOMINAL_FPS usage in
# api.py for where this matters (timecode <-> frame count) versus where the
# exact rate is used instead (frame count -> wall-clock seconds).
NOMINAL_FPS: dict[float, int] = {
    23.976: 24,
    24.0: 24,
    25.0: 25,
    29.97: 30,
    30.0: 30,
    47.95: 48,
    48.0: 48,
    50.0: 50,
    59.94: 60,
    60.0: 60,
    119.88: 120,
    120.0: 120,
}
DEFAULT_FPS = 25.0
