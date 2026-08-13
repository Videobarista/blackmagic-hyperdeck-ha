# Blackmagic HyperDeck voor Home Assistant
Custom integratie (HACS) voor Blackmagic HyperDeck disk recorders (Studio, Extreme, Shuttle, en oudere modellen) via het **HyperDeck Ethernet Protocol** (TCP-poort 9993).

> **v0.2.0**: deze integratie gebruikte in v0.1.0 Blackmagic's nieuwe REST API (december 2024, poort 80). Die zit alleen op recente firmware van de huidige Extreme/Shuttle/Studio-lijn. Het Ethernet-protocol op poort 9993 zit al sinds ~2013 op vrijwel elke HyperDeck met netwerkpoort — oud én nieuw — en is nooit vervangen door REST, alleen aangevuld. Vandaar de overstap: bredere compatibiliteit voor iedereen die deze integratie via HACS installeert.

## Features
- **Media player** entity met play / pause / stop / next / previous / seek, clipnaam, en een live voortgangsbalk.
- **Buttons**: Play, Stop, Record, Next clip, Previous clip, Restart clip — voor eigen dashboard-layouts.
- **Sensors**: Tijdcode, Huidige clip, Transportmodus, Clipvoortgang (%).
- **Switches**: Loop tijdlijn, Loop enkele clip.
- **Realtime updates** via de asynchrone notificaties van het protocol zelf (`notify: transport/slot/configuration/clips/disk`), met een lichte poll (elke 2 s) als aanvulling voor de tijdcode — die stuurt de HyperDeck bewust niet als losse pushnotificatie (dat zou bij elke frame een bericht sturen en de verbinding verstoppen).

## Vereisten
- HyperDeck met ethernet-aansluiting en netwerkverbinding (poort 9993 bereikbaar vanaf Home Assistant).
- Home Assistant 2024.6 of nieuwer.

## Installatie (HACS)
1. HACS → drie puntjes rechtsboven → *Custom repositories*.
2. Voeg de URL van deze repository toe, categorie **Integration**.
3. Installeer *Blackmagic HyperDeck* en herstart Home Assistant.
4. Instellingen → Apparaten & Diensten → *Integratie toevoegen* → **Blackmagic HyperDeck**.
5. Vul het IP-adres van de HyperDeck in (poort 9993 is standaard).

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
De integratie geeft `media_position`, `media_duration` en `media_position_updated_at` door aan Home Assistant; de frontend rekent daar zelf realtime de balk mee uit. De positie binnen de huidige clip hangt af van de `configuration: timecode output`-instelling op het apparaat (`clip` of `timeline`) — die twee gebruiken een andere referentie voor de tijdcode die het protocol teruggeeft. De integratie **leest** die instelling uit bij het verbinden (en houdt 'm actueel via de bijbehorende pushnotificatie) om de tijdcode altijd correct te interpreteren, maar **wijzigt** 'm nooit zelf: dat beïnvloedt namelijk ook wat er op het voorpaneel van het apparaat te zien is, en dat wil je niet stiekem laten veranderen tijdens gebruik.

## Opmerkingen
- **Loop / Loop enkele clip**: het protocol heeft geen los commando om deze twee vlaggen te zetten — ze zijn parameters van het `play`-commando zelf. De switches sturen daarom een `play`-commando met de huidige snelheid ongewijzigd erbij, zodat omzetten terwijl het apparaat stilstaat niet per ongeluk de weergave start. Dit is een echte beperking van het protocol, geen bug.
- **Next/previous/select** clip gaan nu rechtstreeks via `goto: clip id`, native ondersteund door het protocol — geen omweg via seeken meer nodig zoals bij de REST-versie.
- De tijdcode-sensor wordt bewust **niet** via een pushnotificatie geabonneerd (kan per frame binnenkomen); die update via de lichte poll (elke 2 s).
- Record start opname op de actieve media. Wees voorzichtig met de record-knop op gedeelde dashboards.
- De verbinding is één persistente TCP-sessie per HyperDeck; bij verbindingsverlies probeert de integratie elke 10 seconden opnieuw te verbinden.

## License
Released under the [MIT License](LICENSE). Copyright (c) 2026 VideoBarista.
Blackmagic Design, HyperDeck and Blackmagic HyperDeck are trademarks of Blackmagic
Design Pty Ltd. This project is an independent community integration and is
not affiliated with or endorsed by Blackmagic Design.
