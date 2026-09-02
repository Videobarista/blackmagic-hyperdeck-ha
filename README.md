# Blackmagic HyperDeck for Home Assistant
Custom integration (HACS) for Blackmagic HyperDeck disk recorders (Studio, Extreme, Shuttle, and older models) via the **HyperDeck Ethernet Protocol** (TCP port 9993).

> **v0.2.0**: this integration used Blackmagic's new REST API (December 2024, port 80) in v0.1.0. That's only present on recent firmware for the current Extreme/Shuttle/Studio line. The Ethernet Protocol on port 9993 has shipped on virtually every networked HyperDeck since ~2013 — old and new alike — and was never replaced by REST, only supplemented by it. Hence the switch: broader compatibility for anyone installing this integration via HACS.

## Features
- **Media player** entity with play / pause / stop / next / previous / seek, clip name, and a live progress bar.
- **Buttons**: Play, Stop, Record, Next clip, Previous clip, Restart clip — for custom dashboard layouts.
- **Sensors**: Timecode, Current clip, Transport mode, Clip progress (%).
- **Switches**: Loop timeline, Loop single clip.
- **Real-time updates** via the protocol's own asynchronous notifications (`notify: transport/slot/configuration/clips/disk`), with a light poll (every 2 s) as a supplement for the timecode — the HyperDeck deliberately isn't asked to push that as its own notification (that would send a message on every single frame and clog the connection).

## Requirements
- HyperDeck with an ethernet connection and network access (port 9993 reachable from Home Assistant).
- Home Assistant 2024.6 or newer.

## Installation (HACS)
1. HACS → three dots top right → *Custom repositories*.
2. Add this repository's URL, category **Integration**.
3. Install *Blackmagic HyperDeck* and restart Home Assistant.
4. Settings → Devices & Services → *Add integration* → **Blackmagic HyperDeck**.
5. Enter the HyperDeck's IP address (port 9993 is the default).

Manual install also works: copy `custom_components/blackmagic_hyperdeck` to your `config/custom_components/` folder.

## Dashboard examples
### Media control card (progress bar included)
```yaml
type: media-control
entity: media_player.hyperdeck
```

### Tile with a progress-bar feel
The `sensor.hyperdeck_clip_progress` sensor (0–100 %) works well with a gauge or a custom bar card:
```yaml
type: gauge
entity: sensor.hyperdeck_clip_progress
min: 0
max: 100
needle: false
```

Or with [custom:bar-card](https://github.com/custom-cards/bar-card) via HACS for a real filling bar:
```yaml
type: custom:bar-card
entity: sensor.hyperdeck_clip_progress
max: 100
```

### Transport buttons
```yaml
type: horizontal-stack
cards:
  - type: button
    entity: button.hyperdeck_previous_clip
  - type: button
    entity: button.hyperdeck_play
  - type: button
    entity: button.hyperdeck_stop
  - type: button
    entity: button.hyperdeck_record
  - type: button
    entity: button.hyperdeck_next_clip
```

## How the progress bar works
The integration passes `media_position`, `media_duration`, and `media_position_updated_at` to Home Assistant; the frontend calculates the bar itself in real time. Position within the current clip depends on the device's own `configuration: timecode output` setting (`clip` or `timeline`) — the two use a different reference point for the timecode the protocol returns. The integration **reads** that setting on connect (and keeps it current via the matching push notification) so it always interprets the timecode correctly, but it **never changes** it itself: that setting also affects what shows on the device's own front-panel display, and that's not something that should change on you mid-use without asking.

## Notes
- **Loop / Loop single clip**: the protocol has no standalone command to set these two flags — they're parameters of the `play` command itself. The switches therefore send a `play` command with the current speed passed through unchanged, so flipping a switch while the deck is stopped doesn't accidentally start playback. This is a genuine protocol limitation, not a bug.
- **Next/previous/select** clip now go straight through `goto: clip id`, natively supported by the protocol — no more seek-based workaround like the REST version needed.
- The timecode sensor is deliberately **not** subscribed via a push notification (it could arrive every frame); it updates via the light poll (every 2 s) instead.
- Record starts recording on the active media. Be careful with the record button on shared dashboards.
- **Seeking (dragging the progress bar)**: uses `goto: timecode: HH:MM:SS:FF` (absolute timeline position) rather than `goto: clip: {frame}` (clip-relative). On a real older HyperDeck (Studio Pro, protocol 1.8), the latter was rejected as "invalid value" in both a plain-integer and a timecode-string form, while `goto: clip: start` (the keyword form) worked fine - pointing at that specific sub-command rather than the value's shape. This has not yet been confirmed working on real hardware; if it still fails on your deck, that's a known open issue - every other control (play/pause/stop/next/previous/restart/loop) is unaffected.
- The connection is a single persistent TCP session per HyperDeck; on connection loss, the integration retries every 10 seconds.

## License
Released under the [MIT License](LICENSE). Copyright (c) 2026 VideoBarista.
Blackmagic Design, HyperDeck and Blackmagic HyperDeck are trademarks of Blackmagic
Design Pty Ltd. This project is an independent community integration and is
not affiliated with or endorsed by Blackmagic Design.
