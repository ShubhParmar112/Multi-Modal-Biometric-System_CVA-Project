# Wiring Diagram: ESP32 ↔ R307S Fingerprint Sensor

## Component Connections

```
┌──────────────────────────────────────────────────────────────────┐
│                        WIRING DIAGRAM                            │
│              ESP32 DevKit  ↔  R307S Fingerprint Sensor           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ESP32                                    R307S                 │
│   ┌─────────────┐                     ┌──────────────┐          │
│   │             │                     │              │          │
│   │     3.3V ●──┼─── Red Wire ───────┼── VCC (3.3V) │          │
│   │             │                     │              │          │
│   │      GND ●──┼─── Black Wire ─────┼── GND        │          │
│   │             │                     │              │          │
│   │  GPIO 16 ●──┼─── Green Wire ─────┼── TX         │          │
│   │  (RX2)      │                     │              │          │
│   │             │                     │              │          │
│   │  GPIO 17 ●──┼─── White Wire ─────┼── RX         │          │
│   │  (TX2)      │                     │              │          │
│   │             │                     │              │          │
│   │      USB ●──┼─── USB Cable ──────┼── LAPTOP     │          │
│   │             │                     │              │          │
│   └─────────────┘                     └──────────────┘          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Pin Mapping Table

| ESP32 Pin    | R307S Pin | Wire Color | Function              |
|:-------------|:----------|:-----------|:----------------------|
| 3.3V         | VCC       | 🔴 Red     | Power Supply (3.3V)   |
| GND          | GND       | ⚫ Black   | Ground                |
| GPIO 16 (RX2)| TX        | 🟢 Green   | Sensor TX → ESP32 RX  |
| GPIO 17 (TX2)| RX        | ⚪ White   | ESP32 TX → Sensor RX  |
| USB          | -         | Cable      | ESP32 → Laptop (Data) |

## R307S Sensor Pin Identification

The R307S has a **4-pin JST connector** (sometimes 6-pin with unused pins):

```
╔═══════════════════════════════╗
║     R307S Sensor (Top View)   ║
║  ┌─────────────────────────┐  ║
║  │    ┌───────────────┐    │  ║
║  │    │  Scan Window  │    │  ║
║  │    └───────────────┘    │  ║
║  │                         │  ║
║  │  [1] [2] [3] [4]       │  ║
║  └──┼───┼───┼───┼─────────┘  ║
║     │   │   │   │             ║
║   VCC  TX  RX  GND           ║
║   Red Grn Wht Blk            ║
╚═══════════════════════════════╝
```

## Important Notes

> ⚠️ **VOLTAGE WARNING**
> The R307S operates at **3.3V logic**. The ESP32 also uses 3.3V, so
> direct connection is safe. Do NOT connect to 5V — it may damage
> the sensor.

> 📌 **UART CROSSOVER**
> Remember: TX→RX, RX→TX (crossover connection).
> ESP32 RX (GPIO 16) connects to Sensor TX.
> ESP32 TX (GPIO 17) connects to Sensor RX.

> 🔌 **USB CONNECTION**
> The ESP32 connects to your laptop via USB cable.
> This provides both power to ESP32 and serial data communication.
> The R307S is powered from the ESP32's 3.3V pin.

## Breadboard Layout

```
    Breadboard
    ═══════════════════════════════════════════
    
    ESP32 DevKit (plugged into breadboard)
    ┌────────────────────────────────────┐
    │  [EN]  [GPIO 23] ... [GPIO 16] ●──┼──→ R307S TX (Green)
    │  [VP]  [GPIO 22] ... [GPIO 17] ●──┼──→ R307S RX (White)
    │  [VN]  [GPIO 21] ... [GPIO 5]     │
    │  [D34] [GPIO 19] ... [GPIO 18]    │
    │  [D35] [GPIO 3]  ... [GPIO 0]     │
    │  [D32] [GPIO 1]  ... [GPIO 2] LED │
    │  [D33] [GND]     ... [GND]    ●───┼──→ R307S GND (Black)
    │  [D25] [VIN]     ... [3.3V]   ●───┼──→ R307S VCC (Red)
    │  [USB PORT - connects to laptop]  │
    └────────────────────────────────────┘
    
    R307S placed off-breadboard, connected via jumper wires
```

## Additional Hardware (Optional)

| Component     | Purpose                    | Connection        |
|:--------------|:---------------------------|:------------------|
| LED (Green)   | Fingerprint match indicator| GPIO 2 + 220Ω → GND |
| LED (Red)     | Error/no-match indicator   | GPIO 4 + 220Ω → GND |
| Buzzer        | Audio feedback             | GPIO 5 → Buzzer → GND |

## Tested Configurations

- ✅ ESP32 DevKitV1 (30-pin) + R307S
- ✅ ESP32-WROOM-32 + R307S
- ✅ ESP32 NodeMCU-32S + R307S
- ✅ ESP32-S2 (use different UART pins)
