# Blackmagic HyperDeck voor Home Assistant

Custom integratie (HACS) voor Blackmagic HyperDeck disk recorders (Studio, Extreme, Shuttle) via de HyperDeck Control REST API + notification websocket.

## Features

- **Media player** entity met play / pause / stop / next / previous / seek, clipnaam, en een live voortgangsbalk (Home Assistant extrapoleert de positie realtime — geen zware polling nodig).
- **Buttons**: Play, Stop, Record, Next clip, Previous clip, Restart clip — voor eigen dashboard-layouts.
- **Sensors**: Tijdcode, Huidige clip, Transportmodus, Clipvoortgang (%).
- **Switches**: Loop tijdlijn, Loop enkele clip.
- **Realtime updates** via de notification websocket, met polling (5 s) als fallback.

## Vereisten

- HyperDeck met recente firmware (REST API aanwezig, december 2024 spec) en netwerkverbinding.
- Home Assistant 2024.6 of nieuwer.

## Installatie (HACS)

1. HACS → drie puntjes rechtsboven → *Custom repositories*.
2. Voeg de URL van deze repository toe, categorie **Integration**.
3. Installeer *Blackmagic HyperDeck* en herstart Home Assistant.
4. Instellingen → Apparaten & Diensten → *Integratie toevoegen* → **Blackmagic HyperDeck**.
5. Vul het IP-adres van de HyperDeck in (poort 80 is standaard).

Handmatig kan ook: kopieer `custom_components/blackmagic_hyperdeck` naar je `config/custom_components/` map.

## Dashboard-voorbeelden

### Media control card (voortgangsbalk inbegrepen)

```yaml
type: media-control
entity: media_player.hyperdeck
```

### Tile met voortgangsbalk-gevoel

De sensor `sensor.hyperdeck_clip_progress` (0–100 %) werkt goed met een gauge of een custom bar card:

```yaml
type: gauge
entity: sensor.hyperdeck_clip_progress
min: 0
max: 100
needle: false
```

Of met [custom:bar-card](https://github.com/custom-cards/bar-card) via HACS voor een echte oplopende balk:

```yaml
type: custom:bar-card
entity: sensor.hyperdeck_clip_progress
max: 100
```

### Transport-knoppen

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

## Hoe de voortgangsbalk werkt

De integratie geeft `media_position`, `media_duration` en `media_position_updated_at` door aan Home Assistant. De frontend rekent daar zelf realtime de balk mee uit — er is dus **geen** seconde-polling nodig. De `clip_progress` sensor (voor tiles/gauges) update bij elke websocket-push of poll (max. elke 5 s).

## Opmerkingen

- Next/previous bestaat niet letterlijk in de REST API; de integratie springt naar het startframe van de vorige/volgende clip op de tijdlijn via seek.
- De tijdcode-property wordt bewust **niet** via de websocket geabonneerd (kan per frame pushen); de tijdcodesensor update per poll.
- Record start opname op de actieve media. Wees voorzichtig met de record-knop op gedeelde dashboards.

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 HuisAutomatisering.

Blackmagic Design, Videohub and Smart Videohub are trademarks of Blackmagic
Design Pty Ltd. This project is an independent community integration and is
not affiliated with or endorsed by Blackmagic Design.
