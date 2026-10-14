# Blackmagic HyperDeck for Home Assistant

[![Tests](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/tests.yml)
[![Ruff](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/ruff.yml/badge.svg?branch=main)](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/ruff.yml)
[![Hassfest](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/hassfest.yml/badge.svg?branch=main)](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/hassfest.yml)
[![HACS](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/hacs.yml/badge.svg?branch=main)](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/hacs.yml)
[![CodeQL](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/Videobarista/blackmagic-hyperdeck-ha/actions/workflows/codeql.yml)
[![Quality scale: Bronze aligned](https://img.shields.io/badge/quality%20scale-Bronze%20aligned-cd7f32)](#quality-scale)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub release](https://img.shields.io/github/v/release/Videobarista/blackmagic-hyperdeck-ha)](https://github.com/Videobarista/blackmagic-hyperdeck-ha/releases)
[![License: MIT](https://img.shields.io/github/license/Videobarista/blackmagic-hyperdeck-ha)](LICENSE)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Videobarista&repository=blackmagic-hyperdeck-ha&category=integration)

Custom integration (HACS) for Blackmagic HyperDeck disk recorders (Studio, Extreme, Shuttle, and older models) via the **HyperDeck Ethernet Protocol** (TCP port 9993).

## Features
- **Media player** entity with play / pause / stop / next / previous / seek, clip name, and a live progress bar.
- **Buttons**: Play, Stop, Record, Next clip, Previous clip, Restart clip — for custom dashboard layouts.
- **Sensors**: Timecode, Current clip, Transport mode, Clip progress (%).
- **Switches**: Loop timeline, Loop single clip.
- **Real-time updates** via the protocol's own asynchronous notifications (`notify: transport/slot/configuration`), with a light poll (every 2 s) as a supplement for the timecode — the HyperDeck deliberately isn't asked to push that as its own notification (that would send a message on every single frame and clog the connection).

## Requirements
- HyperDeck with an ethernet connection and network access (port 9993 reachable from Home Assistant).
- Home Assistant 2024.6 or newer.

## Installation (HACS)
Click the **Open in HACS** button above, or add it by hand:

1. HACS → three dots top right → *Custom repositories*.
2. Add this repository's URL, category **Integration**.
3. Install *Blackmagic HyperDeck* and restart Home Assistant.
4. Settings → Devices & Services → *Add integration* → **Blackmagic HyperDeck**.
5. Enter the HyperDeck's IP address (port 9993 is the default).

Manual install also works: copy `custom_components/blackmagic_hyperdeck` to your `config/custom_components/` folder.

## Removal
1. Settings → Devices & Services → **Blackmagic HyperDeck** → three dots next to each HyperDeck → *Delete*.
2. In HACS, open *Blackmagic HyperDeck* → three dots → *Remove*, then restart Home Assistant.

The integration stores nothing outside its own config entries, so nothing else needs cleaning up.

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
- **Why the Ethernet Protocol and not the REST API**: Blackmagic's newer REST API (port 80) only exists on recent firmware for the current Extreme/Shuttle/Studio line. The classic HyperDeck Ethernet Protocol on port 9993 has shipped on virtually every networked HyperDeck since around 2013, old and new alike, and was never replaced by REST, only supplemented by it. Using it keeps this integration working on older decks too. It is also deliberately limited to commands that older firmware understands (tested on a HyperDeck Studio Pro reporting protocol version 1.8).
- **Loop / Loop single clip**: the protocol has no standalone command to set these two flags — they're parameters of the `play` command itself. The switches therefore send a `play` command with the current speed passed through unchanged, so flipping a switch while the deck is stopped doesn't accidentally start playback. This is a genuine protocol limitation, not a bug.
- **Next/previous/select** clip go straight through `goto: clip id`, natively supported by the protocol.
- The timecode sensor is deliberately **not** subscribed via a push notification (it could arrive every frame); it updates via the light poll (every 2 s) instead.
- Record starts recording on the active media. Be careful with the record button on shared dashboards.
- When the deck is unreachable (powered off, unplugged, network down), the media player shows **Off** rather than the grey "Unavailable" badge - a HyperDeck being off is an expected, normal state, not an integration error. This also applies when the deck is already off while Home Assistant starts: setup does not fail, and the integration keeps reconnecting every 10 seconds in the background. Buttons, switches, and sensors show as unavailable while disconnected, since there's nothing to press or display for those. Going offline and coming back are each logged once at info level, not as errors.
- Works fine with no media inserted: on at least one real deck, the "no disk" condition ("105 no disk") can be returned by more than one status query during setup, depending on firmware/state - not just "clips get". Every query used during setup and polling tolerates this and falls back to an empty/default value rather than failing.
- Pressing a control (play, record, seek, ...) that the deck rejects outright - most commonly "105 no disk" with no media inserted - is logged at debug level only, not as an error. This is an expected, everyday occurrence for hardware like this, not a bug worth an ERROR-level traceback per press.
- **Seeking (dragging the progress bar)**: uses `goto: timecode: HH:MM:SS:FF` (absolute timeline position) rather than `goto: clip: {frame}` (clip-relative). On a real older HyperDeck (Studio Pro, protocol 1.8), the latter was rejected as "invalid value" in both a plain-integer and a timecode-string form, while `goto: clip: start` (the keyword form) worked fine - pointing at that specific sub-command rather than the value's shape. Confirmed working on real hardware with the `goto: timecode:` approach.
- **Next clip** on a single-clip timeline: the deck clamps `goto: clip id: +1` to the current clip when there's nothing beyond it (per the protocol spec), so pressing "next" with only one clip on the timeline is a no-op rather than an error - expected behavior, not a bug.
- The connection is a single persistent TCP session per HyperDeck; on connection loss, the integration retries every 10 seconds.

## Quality scale
This integration is aligned with the Home Assistant quality scale: **Bronze**. Home Assistant only grades core integrations, so this is a self-assessment, not an official tier. See [`quality_scale.yaml`](custom_components/blackmagic_hyperdeck/quality_scale.yaml) for the rule-by-rule status.

One deliberate deviation: the `test-before-setup` rule would make setup fail while a HyperDeck is switched off. In a production environment a powered-off deck is normal, so this integration sets up anyway and reconnects in the background instead (the connection is still verified when you first add the deck).

## License
Released under the [MIT License](LICENSE). Copyright (c) 2026 Videobarista.
Blackmagic Design, HyperDeck and Blackmagic HyperDeck are trademarks of Blackmagic
Design Pty Ltd. This project is an independent community integration and is
not affiliated with or endorsed by Blackmagic Design.
