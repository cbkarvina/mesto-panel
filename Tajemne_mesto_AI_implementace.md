# Dokumentace pro AI implementaci

## Projekt: Tajemné město -- Mission Control System

**Verze:** 1.0

## 1. Cíl projektu

Vyvinout modulární řídicí centrum pro dětskou hru na Raspberry Pi.

### Hlavní cíle

-   Oddělit hardware od herní logiky.
-   Ovládat panel přes síť.
-   Podporovat rozšiřitelné mise.
-   Používat event-driven architekturu.

## 2. Architektura

``` text
Web Dashboard
      │
REST API + WebSocket
      │
FastAPI Server
      │
 ├── Game Engine
 └── Hardware Layer
        ├── MCP23017
        ├── WS2812B
        ├── MAX7219
        ├── OLED
        └── Rotary Encoders
```

## 3. Struktura projektu

``` text
city-control/
    app.py
    server/
    engine/
    missions/
    hardware/
    dashboard/
    config/
    data/
```

## 4. Hlavní vrstvy

### Hardware Layer

-   MCP23017
-   WS2812B
-   MAX7219
-   OLED
-   Rotary Encoders

Nikdy neobsahuje herní logiku.

### Game Engine

Řídí: - mise - fragmenty - časovače - alarmy - stav města

### Mission Plugins

Každá mise implementuje:

``` python
start()
stop()
handle_event()
tick()
serialize()
```

## 5. Event Bus

Události: - ButtonPressed - ButtonReleased - SwitchChanged -
EncoderChanged - MissionStarted - MissionFinished - FragmentUnlocked -
AlarmTriggered

## 6. Hardware

### Raspberry Pi 3B

### MCP23017

Software debounce.

### WS2812B

Segmenty: - power - transport - communication - rescue - core - alarm

### MAX7219

Použití: - Morse - animace - diagnostika - zadávání kódu

### Rotary Encoders

3 kusy.

### OLED

Instrukce, časovače, stav mise.

## 7. REST API

-   GET /api/status
-   GET /api/inputs
-   GET /api/leds
-   POST /api/mission/start
-   POST /api/system/status
-   POST /api/fragment/unlock

## 8. WebSocket

Živé události: - ButtonPressed - MissionUpdated - AlarmStarted -
LEDChanged - FragmentUnlocked

## 9. Dashboard

Obsahuje: - Přehled města - Stav systémů - Stav vstupů - Log událostí -
Ovládání misí - Fragmenty

## 10. LED API

``` python
set_system_status()
set_power_level()
flash_alarm()
pulse()
show_fragment()
show_success()
show_failure()
```

## 11. Input API

``` python
ButtonPressed
ButtonReleased
SwitchChanged
EncoderChanged
```

## 12. Mise

Každá implementuje:

``` python
start()
update()
handle_event()
stop()
```

## 13. Zadávání kódu

Hardware: - 3 rotační enkodéry - tlačítko - MAX7219

Režimy: - synchronizace generátorů - ladění antény - kombinace sejfu -
kalibrace - městský kód

## 14. Konfigurace

YAML: - leds.yaml - inputs.yaml - missions.yaml - panel.yaml

## 15. Persistování

game_state.json

Obsah: - stav systémů - fragmenty - čas - aktivní mise

## 16. Programovací zásady

-   Python 3.12+
-   FastAPI
-   WebSocket
-   Pydantic
-   dataclasses
-   typing
-   logging
-   YAML konfigurace
-   Event-driven architektura
-   Oddělení hardware a logiky
