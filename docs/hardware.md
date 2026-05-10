# Hardware — pin map & wiring notes

> This file is the **authoritative** pin map for the code (`src/hardware/pins.py` mirrors it).
> The Notion brief is the design narrative; if they disagree, fix Notion to match this.

## Important corrections vs. the original brief

1. **The Jetson Nano has no analog input pins.** "Pin A0/A1/A2" from the brief doesn't exist on a Nano.
   - DHT11/DHT22 and PIR are *digital* — they go on regular GPIO pins, fine.
   - **MQ2 is analog** (it outputs a voltage proportional to gas concentration, plus a digital "threshold crossed" line). The analog `AOUT` must go through an external ADC. Plan: **ADS1115** (4-channel 16-bit I²C ADC) on the Jetson's I²C bus. The MQ2 `DOUT` (digital comparator) can additionally go on a spare GPIO if we want a fast threshold interrupt.
2. **Sensor naming:** start with **DHT11** (cheap, in inventory), swap to **DHT22** later for accuracy. Code should treat the model as a config value, not hard-code it.
3. **Gas sensor:** **MQ2** (smoke / LPG / methane / alcohol / H₂), *not* MQ-135 — MQ2 reacts to everyday smoke/lighter events that demo well on camera.
4. **Relays drive nothing on the AC side.** The relay *click* + the module's onboard indicator LED is the on-camera proof that the agent acted. Pin numbers below are the relay module's control inputs.
5. **GPIO numbering:** numbers below are **BOARD pin numbers** (the physical 40-pin header), which is what `Jetson.GPIO` uses with `GPIO.setmode(GPIO.BOARD)`. Adjust once the wiring is finalized on the bench.

## Sensors

| Sensor | Connection | Jetson pin (BOARD) | Notes |
|---|---|---|---|
| DHT11 (→ DHT22) | 1-wire data | TBD (e.g. 7) | digital; needs a pull-up (10k) on data |
| PIR motion | digital OUT | TBD (e.g. 11) | 3.3V logic; warm-up ~30–60 s after power |
| MQ2 — analog | `AOUT` → ADS1115 ch A0 | I²C (pins 3 SDA / 5 SCL) | ADS1115 addr 0x48; MQ2 needs ~24–48 h burn-in for stable readings, ~minutes warm-up each boot |
| MQ2 — digital | `DOUT` | TBD (e.g. 13) | optional fast threshold line; pot on the module sets the trip point |
| Rotary encoder | A / B / SW | TBD (e.g. 16 / 18 / 22) | quadrature A/B + push switch; debounce in software |
| Logitech C270 | USB | — | `/dev/video0`; only used by the vision-aware variant |

## Actuators

| Actuator | Connection | Jetson pin (BOARD) | Notes |
|---|---|---|---|
| Relay 1 — "Fan" | relay module IN1 | TBD (e.g. 29) | most cheap relay boards are **active-LOW** (drive LOW = energize); confirm on the bench |
| Relay 2 — "Lamp" | relay module IN2 | TBD (e.g. 31) | same |
| (Relay 3 / 4 spare) | IN3 / IN4 | TBD | 4-channel module; spares for future loads |
| LED strip | data / gate | TBD (e.g. 33) | if it's an addressable strip (WS2812) it needs precise timing — likely a small MCU or a PWM-friendly approach; if it's a plain 12V strip, switch it via a MOSFET/relay |
| Passive buzzer | signal | TBD (e.g. 32 — PWM) | passive buzzer needs a PWM/tone signal, not just HIGH/LOW |

## Power notes

- MQ2 has a heater coil — budget ~150 mA @ 5V *per sensor*; don't power it from a 3.3V rail. Use the Jetson 5V pin only if the supply has headroom, otherwise a separate 5V supply with common ground.
- Relay module: power the relay coils from 5V (often a separate `JD-VCC`), keep the logic side referenced to the Jetson's 3.3V GPIO; many boards have an opto-isolator + jumper for exactly this.
- The Jetson Nano + HDMI display + USB webcam already pull a fair bit; use a solid 5V/4A barrel supply (not micro-USB) and don't hang the relay coils + MQ2 heaters off the Jetson's 5V pins.

## I²C / buses in use

| Bus | Device | Address | Purpose |
|---|---|---|---|
| I²C-1 (pins 3/5) | ADS1115 | 0x48 | MQ2 analog read (and headroom for 3 more analog sensors — LDR, etc.) |

## TODO before writing sensor/actuator code

- [ ] Bench-confirm relay module polarity (active-LOW vs active-HIGH)
- [ ] Decide LED strip type (addressable vs plain) — drives the wiring + library choice
- [ ] Confirm `Jetson.GPIO` PWM availability on the Nano for the passive buzzer (limited HW PWM pins; may need software PWM or a tone via a timer)
- [ ] Lock the actual header pins and update this table + `src/hardware/pins.py`
- [ ] Verify ADS1115 + `adafruit-circuitpython-ads1x15` works under the Jetson's Python (3.6.9) or a venv
