# Blackmagic HyperDeck for Home Assistant
Custom integration (HACS) for Blackmagic HyperDeck disk recorders (Studio, Extreme, Shuttle) via the HyperDeck Control REST API + notification websocket.

## Features
- **Media player** entity with play / pause / stop / next / previous / seek, clip name, and a live progress bar (Home Assistant extrapolates the position in real time — no heavy polling needed).
- **Buttons**: Play, Stop, Record, Next clip, Previous clip, Restart clip — for custom dashboard layouts.
- **Sensors**: Timecode, Current clip, Transport mode, Clip progress (%).
- **Switches**: Loop timeline, Loop single clip.
- **Real-time updates** via the notification websocket, with polling (5 s) as a fallback.

## Requirements
- HyperDeck with recent firmware (REST API present, December 2024 spec) and a network connection.
- Home Assistant 2024.6 or newer.

## Installation (HACS)
1. HACS → three dots top right → *Custom repositories*.
2. Add this repository's URL, category **Integration**.
3. Install *Blackmagic HyperDeck* and restart Home Assistant.
4. Settings → Devices & Services → *Add integration* → **Blackmagic HyperDeck**.
5. Enter the HyperDeck's IP address (port 80 is default).

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
The integration passes `media_position`, `media_duration`, and `media_position_updated_at` to Home Assistant. The frontend calculates the bar itself in real time — so **no** per-second polling is needed. The `clip_progress` sensor (for tiles/gauges) updates on every websocket push or poll (every 5 s at most).

## Notes
- Next/previous doesn't literally exist in the REST API; the integration seeks to the start frame of the previous/next clip on the timeline instead.
- The timecode property is deliberately **not** subscribed via the websocket (it can push per frame); the timecode sensor updates on each poll.
- Record starts recording on the active media. Be careful with the record button on shared dashboards.

## License
Released under the [MIT License](LICENSE). Copyright (c) 2026 HuisAutomatisering.

Blackmagic Design, HyperDeck and Blackmagic HyperDeck are trademarks of Blackmagic
Design Pty Ltd. This project is an independent community integration and is
not affiliated with or endorsed by Blackmagic Design.
