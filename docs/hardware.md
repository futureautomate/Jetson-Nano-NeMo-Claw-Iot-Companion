# Hardware — pin map & wiring notes

> **Authoritative** pin map for the code. `src/hardware/pins.py` mirrors this file.
> Synced to the Notion brief (Project Tracker) as of 2026-05-10 — keep them in step.
>
> All pin numbers are **BOARD numbers** (physical position on the Jetson Nano 40-pin
> header) — i.e. what `Jetson.GPIO` uses after `GPIO.setmode(GPIO.BOARD)`. BCM numbers
> are given in parentheses for reference. The Jetson Nano has **no analog pins**, so the
> MQ2 analog level is read via an **ADS1115 I²C ADC** on physical pins 3 (SDA) / 5 (SCL).

## Hardware substitutions vs. the original concept
- **DHT11** now (DHT22 is a drop-in upgrade later — treated as a config value, not hard-coded).
- **MQ2** instead of MQ-135 — reacts to everyday smoke/lighter events that demo well on camera.
- **ADS1115 I²C ADC** added — required because the Nano can't read the MQ2's analog output directly.

## Sensors

| Sensor | Interface | Pin (BOARD / BCM) | Wiring notes |
|---|---|---|---|
| DHT11 (→ DHT22) | digital 1-wire | **7** (BCM 4) | 4.7 kΩ pull-up from data → 3.3 V; module powered from 3.3 V or 5 V (data is 3.3 V-safe) |
| PIR motion (HC-SR501) | digital in | **11** (BCM 17) | module powered from 5 V; OUT is usually 3.3 V — *verify*; ~30–60 s warm-up after power |
| MQ2 — digital `DO` | digital in | **13** (BCM 27) | HIGH when gas/smoke crosses the onboard pot threshold — fast hardware-level trigger |
| MQ2 — analog `AO` | I²C via ADS1115 | **ADS1115 ch A0** (I²C pins 3 SDA / 5 SCL) | continuous level for trend reasoning; ADS1115 addr **0x48** (ADDR→GND). If `AO` swings to 5 V, add a divider — Jetson + ADS1115 @3.3 V can't take 5 V |
| Rotary encoder `A` | digital in | **29** (BCM 5) | quadrature A; debounce in software |
| Rotary encoder `B` | digital in | **31** (BCM 6) | quadrature B |
| Rotary encoder `SW` | digital in | **33** (BCM 13) | push switch (active-LOW with internal pull-up); encoder VCC→3.3 V |
| Logitech C270 | USB | `/dev/video0` | optional — only the vision-aware variant uses it |

## Actuators

| Actuator | Interface | Pin (BOARD / BCM) | Wiring notes |
|---|---|---|---|
| Relay 1 — "Fan" | digital out | **16** (BCM 23) | relay module IN1; VCC→5 V, GND→GND. **No AC load** — relay click + onboard LED is the proof. Most cheap boards are **active-LOW** — *confirm on bench* |
| Relay 2 — "Lamp" | digital out | **18** (BCM 24) | relay module IN2; same notes as Relay 1 |
| LED strip (WS2812) | SPI MOSI | **19** (BCM 10, SPI0 MOSI) | drive WS2812 data off SPI MOSI — the reliable approach on Jetson (Python can't bit-bang the timing). **5 V power from an external supply, not the Jetson 5 V rail**; common ground. See library note below |
| Passive buzzer | digital out / PWM | **22** (BCM 25) | passive buzzer wants a tone/PWM signal, not steady HIGH/LOW; GND→GND |

## I²C / SPI buses in use

| Bus | Pins (BOARD) | Device | Address | Purpose |
|---|---|---|---|---|
| I²C-1 | 3 (SDA), 5 (SCL) | ADS1115 | 0x48 | MQ2 analog read — 3 spare channels (A1–A3) for future analog sensors (LDR, etc.) |
| SPI0 | 19 (MOSI), 23 (SCLK), 24 (CS0) | WS2812 LED strip | — | only MOSI is used for WS2812; enable SPI0 via `jetson-io` |

> ⚠️ The encoder uses pins 29/31/33; the LED strip data is on pin 19 (SPI MOSI) — earlier drafts had the LED on 33, that's now the encoder switch. Don't double-book pins when adding things.

## Enabling I²C / SPI on the Nano

JetPack usually has I²C-1 enabled by default. If `i2cdetect -y -r 1` doesn't show `0x48`, or to enable SPI0 for the LED strip:

```bash
sudo /opt/nvidia/jetson-io/jetson-io.py     # enable "spi1" (header SPI0) ; reboot after
i2cdetect -y -r 1                            # expect UU/-- grid with 0x48 once ADS1115 is wired
```

## LED strip library note

The Notion brief lists `rpi_ws281x` / `adafruit-circuitpython-neopixel` — but on the Jetson Nano:
- `rpi_ws281x` is Raspberry-Pi-specific (uses the Pi's PWM/PCM/SPI DMA) — **won't work**.
- Plain `adafruit-circuitpython-neopixel` bit-bangs from Python — too jittery on the Nano.
- ✅ Use **`adafruit-circuitpython-neopixel-spi`**, driving WS2812 data from SPI0 MOSI (pin 19). That's the path `requirements.txt` / `jetson_bootstrap.sh` should converge on. (If the strip is actually a plain 12 V analog strip rather than WS2812, switch it with a logic-level MOSFET instead and ignore all of this.)

## Power budget reminders
- MQ2 heater ≈ 150 mA @ 5 V *per sensor* — needs 5 V, not 3.3 V. Don't hang it (or the relay coils, or the LED strip) off the Jetson's 5 V header pins; use a separate 5 V supply with common ground.
- Jetson Nano + HDMI display + USB webcam already pulls a fair bit — power the Nano from a solid 5 V/4 A barrel-jack supply (set `J48` jumper), not micro-USB.
- Relay module: power the coil side from 5 V (often a separate `JD-VCC`), keep the logic side referenced to the Jetson's 3.3 V; use the opto-isolator jumper if the board has one.

## TODO before writing sensor/actuator code
- [ ] Bench-confirm relay module polarity (active-LOW vs active-HIGH) → `active_low` in `pins.py`
- [ ] Confirm PIR `OUT` and MQ2 `DO` are ≤3.3 V (add a divider/level-shifter if 5 V)
- [ ] Confirm WS2812 vs plain 12 V strip → drives the library + wiring choice
- [ ] Decide buzzer drive: HW PWM pin vs software PWM vs a simple transistor + tone
- [ ] Verify `adafruit-circuitpython-ads1x15` + `adafruit-blinka` run under the Nano's Python 3.6.9 (else: venv with newer Python, or Docker)
- [ ] Run `jetson-io` to enable SPI0 if the LED strip is WS2812-on-SPI
