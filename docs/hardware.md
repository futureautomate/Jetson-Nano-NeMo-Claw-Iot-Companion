# Hardware — pin map & wiring notes (v1 build)

> **Authoritative** pin map for the code. `src/hardware/pins.py` mirrors this file.
> v1 uses **only parts already in the IOT inventory** — no purchases.
>
> All pin numbers are **BOARD numbers** (physical position on the Jetson Nano 40-pin
> header) — i.e. what `Jetson.GPIO` uses after `GPIO.setmode(GPIO.BOARD)`. BCM numbers
> are in parentheses for reference. **The Jetson Nano has no analog pins**; every sensor
> below uses a digital line, and the gas/sound/light sensors use their module's *digital
> threshold output* (a small pot on each board sets the trip point).

## v1 scope decisions
- **MQ2 → digital output (`DO`) only.** There's no ADS1115/ADC in inventory, so the analog `AO` level isn't read. (Add an ADS1115 on I²C pins 3/5 → ch A0 later if you want a continuous trend graph.)
- **"Fan" actuator = a real low-voltage DC motor through an L293D**, not an empty relay click. It visibly spins (PWM-controlled speed), it's 5–6 V so it's safe on camera, and it's far more convincing than a relay that switches nothing. Motors ×8 and L293D drivers ×2 are in inventory.
- **"Lamp" actuator = relay channel 1** — the relay *click* + the module's onboard indicator LED is the on-camera proof. No AC load.
- **Buzzer** = the 5 V passive buzzer (needs a tone/PWM signal).
- **Optional mood light** = the LED strip switched on/off via relay channel 2 (only if/when wired; the strip's exact type is unconfirmed — if it turns out to be addressable WS2812 we'd switch to an SPI-MOSI drive instead of a relay).
- **DHT11** now; DHT22 is a drop-in upgrade later (model is a config value, not hard-coded).
- **Camera / vision variant deferred** to a later phase.

## Sensors

| Sensor | Interface | Pin (BOARD / BCM) | Wiring notes |
|---|---|---|---|
| DHT11 (→ DHT22 later) | digital 1-wire (bit-bang) | **7** (BCM 4) | 4.7 kΩ pull-up from data → 3.3 V; VCC 3.3–5 V. Reads are flaky in pure Python on Linux — the reader retries. |
| PIR motion (HC-SR501) | digital in | **11** (BCM 17) | OUT → pin 11; module VCC 5 V (verify OUT ≤ 3.3 V, add a divider if not); ~30–60 s warm-up after power |
| MQ2 gas/smoke — `DO` | digital in (threshold) | **13** (BCM 27) | DO → pin 13; `AO` unused; set the trip point with the pot on the board; needs a few minutes' warm-up (and ~24–48 h burn-in for a stable point) |
| Sound detector — `DO` | digital in (threshold) | **15** (BCM 22) | DO → pin 15; `AO` unused; tune the pot so a clap trips it |
| LDR light module — `DO` | digital in (threshold) | **22** (BCM 25) | DO → pin 22; `AO` unused; set the pot to the desk's "dark" point (DO typically LOW when bright) |
| Rotary encoder `A` | digital in | **29** (BCM 5) | quadrature A; internal pull-up; debounce in software |
| Rotary encoder `B` | digital in | **31** (BCM 6) | quadrature B |
| Rotary encoder `SW` | digital in | **36** (BCM 16) | push switch (active-LOW, internal pull-up); encoder VCC → 3.3 V |
| *(camera — deferred)* | USB / CSI | — | not in v1 |

## Actuators

| Actuator | Interface | Pin (BOARD / BCM) | Wiring notes |
|---|---|---|---|
| **Fan** — DC motor via L293D | H-bridge (PWM speed) | **EN1 → 32** (BCM 12), **IN1 → 35** (BCM 19), **IN2 → 37** (BCM 26) | motor on L293D `OUT1`/`OUT2`; L293D `VCC2` (motor V+) from a **separate 5–6 V supply**, **common ground** with the Jetson; `VCC1` (logic) 3.3–5 V. EN1 PWM @ ~1 kHz sets speed; IN1=HIGH/IN2=LOW = one direction (a fan only needs one). |
| **Lamp** — relay ch1 | digital out | **16** (BCM 23) | relay module `IN1` → pin 16; module VCC 5 V, GND common. **No AC load** — relay click + onboard LED is the proof. Most cheap boards are **active-LOW** — *confirm on bench* (`active_low` in `pins.py`). |
| **Buzzer** — passive | PWM / tone | **33** (BCM 13) | signal → pin 33, GND common; passive buzzer needs a tone/PWM signal, not steady HIGH |
| *Mood light* (optional) — LED strip via relay ch2 | digital out | **18** (BCM 24) | strip switched by relay `IN2` → pin 18; strip from its own supply, common ground. `enabled=False` in `pins.py` until wired. |

## Spare header pins (for adding more devices later)
BOARD pins **12** (BCM 18), **19** (BCM 10 / SPI MOSI), **21** (BCM 9 / SPI MISO), **23** (BCM 11 / SPI SCLK), **24** (BCM 8 / SPI CS0), **26** (BCM 7 / SPI CS1), **38** (BCM 20), **40** (BCM 21) are free. I²C-1 (pins 3 SDA / 5 SCL) is free for a BMP180 pressure sensor or a future ADS1115. UART is on pins 8/10.

> ⚠️ Don't double-book pins when adding things. Current allocation: 7, 11, 13, 15, 16, 18, 22, 29, 31, 32, 33, 35, 36, 37. The encoder switch is on **36** (earlier drafts had it on 33 — that's now the buzzer).

## Power budget reminders
- MQ2 has a heater coil — ~150 mA @ 5 V. Power it from 5 V (not 3.3 V).
- The DC motor: don't run it off the Jetson's 5 V header pins — give the L293D `VCC2` its own 5–6 V supply (battery pack or a buck module from inventory), tied to a common ground.
- Relay coils: power from 5 V (often a separate `JD-VCC`), keep the logic side referenced to the Jetson's 3.3 V; use the opto-isolator jumper if the board has one.
- Power the Jetson Nano itself from a solid 5 V/4 A barrel-jack supply (set the `J48` jumper), not micro-USB — it's also driving the HDMI display + USB.

## Software stack (settled)
- `Jetson.GPIO` (preinstalled on JetPack) — relays, buzzer PWM, motor PWM/dir, all digital sensor inputs, encoder.
- A small **bit-bang DHT11 reader** using `Jetson.GPIO` + retries — see `src/hardware/sensors.py`. (No `adafruit-blinka` / CircuitPython — that stack doesn't install on the Nano's Python 3.6.)
- `python3-smbus` (apt) — reserved for any future I²C sensor (e.g. BMP180).
- `python3-pyqt5` (apt, 5.10) — the HDMI dashboard. `python-telegram-bot` (pip --user) — alerts.
- NemoClaw runs in its own sandbox (its own Python) — installed via `curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`; our code talks to it via the `nemoclaw` / `openclaw` CLI.

## TODO before/while writing the rest of the code
- [ ] Bench-confirm relay module polarity (active-LOW vs active-HIGH) → `active_low` in `pins.py`
- [ ] Confirm PIR `OUT` (and sound/LDR `DO`) are ≤ 3.3 V into the Jetson (add a divider/level-shifter if 5 V)
- [ ] Decide a buzzer drive that doesn't fight the motor PWM (both are software PWM on different pins — fine, just watch CPU)
- [ ] If/when the LED strip is wired: confirm it's a plain strip (relay/MOSFET on/off is enough) vs addressable
- [ ] Wire the bench, then sanity-run `python3 -m src.main --selftest` on the Jetson
