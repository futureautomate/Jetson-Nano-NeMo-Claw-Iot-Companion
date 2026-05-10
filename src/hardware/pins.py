"""Single source of truth for the GPIO pin map (v1 build).

Mirrors docs/hardware.md. Pin numbers are BOARD numbers (physical position on the
Jetson Nano 40-pin header) — what Jetson.GPIO uses after GPIO.setmode(GPIO.BOARD).
BCM numbers are kept alongside for reference.

v1 scope (only parts already in the IOT inventory):
  * 5 digital sensors: DHT11, PIR, MQ2 (digital DO only — no ADS1115 in inventory),
    sound detector, LDR module + a rotary encoder for manual override.
  * 3 actuators: "fan" = a real low-voltage DC motor driven through an L293D
    (visibly spins), "lamp" = a relay channel (click + onboard LED), a passive
    buzzer. Optional 4th: an LED strip on a second relay channel as a mood light.
  * Hardware layer = Jetson.GPIO + a bit-bang DHT11 reader (no Blinka/CircuitPython
    — that stack doesn't run on the Nano's Python 3.6) + python3-smbus for any
    future I2C sensor (e.g. BMP180).

Kept deliberately plain (dicts, py3.6-safe — no dataclasses) so the agent's
runtime hardware-registration path can build on the same structures.

Pins are LOCKED for v1, but a couple of electrical details are still "confirm on
bench" — see the TODO list in docs/hardware.md.
"""

# kind:  "sensor" | "actuator"
# iface: "digital_in" | "digital_out" | "pwm" | "h_bridge" | "i2c" | "usb"
# pin:   BOARD pin number (or None for multi-pin / bus / USB devices)
# bcm:   BCM/GPIO number (reference only)
# pull:  suggested input pull resistor ("up" | "down" | None) for digital_in
# active_low: True if the device asserts on a LOW signal

# --------------------------------------------------------------------------
# SENSORS
# --------------------------------------------------------------------------
SENSORS = {
    "dht": {
        "kind": "sensor", "iface": "digital_in", "pin": 7, "bcm": 4, "pull": None,
        "model": "DHT11", "protocol": "bitbang",  # DHT22 is a drop-in upgrade later
        "reads": ["temperature_c", "humidity_pct"],
        "wiring": "1-wire data -> pin 7; 4.7k pull-up to 3.3V on the data line; VCC 3.3-5V",
        "desc": "Desk temperature & humidity (reads are flaky in pure Python on Jetson — retry)",
    },
    "pir": {
        "kind": "sensor", "iface": "digital_in", "pin": 11, "bcm": 17, "pull": None,
        "model": "HC-SR501",
        "reads": ["motion"],  # HIGH = motion
        "wiring": "OUT -> pin 11; VCC 5V (verify OUT <=3.3V); ~30-60s warm-up after power",
        "desc": "Desk occupancy / motion detection",
    },
    "mq2": {
        "kind": "sensor", "iface": "digital_in", "pin": 13, "bcm": 27, "pull": None,
        "model": "MQ2 (digital output)", "active_low": False,
        "reads": ["gas_alarm"],  # HIGH when gas/smoke crosses the onboard pot threshold
        "wiring": "DO -> pin 13; AO unused (no ADC in inventory); set trip point with the pot; ~minutes warm-up, needs burn-in",
        "desc": "Smoke / LPG / methane / alcohol / H2 threshold alarm. Light a match near it to demo.",
        "note": "If a trend graph is wanted later: add an ADS1115 on I2C (pins 3/5) and read AO on ch A0.",
    },
    "sound": {
        "kind": "sensor", "iface": "digital_in", "pin": 15, "bcm": 22, "pull": None,
        "model": "sound detection sensor (LM393)", "active_low": False,
        "reads": ["sound_alarm"],  # HIGH on a loud sound (clap) — trip point set by the pot
        "wiring": "DO -> pin 15; AO unused; tune the pot so a clap trips it",
        "desc": "Clap / loud-noise detector — great on-camera 'wake' trigger",
    },
    "ldr": {
        "kind": "sensor", "iface": "digital_in", "pin": 22, "bcm": 25, "pull": None,
        "model": "LDR light-sensor module (LM393)", "active_low": True,  # DO LOW when bright (typical)
        "reads": ["is_dark"],  # via DO threshold (pot-set); AO unused (no ADC)
        "wiring": "DO -> pin 22; AO unused; set the pot to the desk's 'dark' point",
        "desc": "Ambient light level (dark/bright) — drives 'turn the lamp on when it's dark'",
    },
    "encoder": {
        "kind": "sensor", "iface": "digital_in", "pin": None,
        "model": "M274 incremental rotary encoder",
        "pins": {"a": 29, "b": 31, "sw": 36}, "bcm": {"a": 5, "b": 6, "sw": 16},
        "pull": "up",
        "reads": ["delta", "button"],
        "wiring": "A->29, B->31, SW->36 (push, active-LOW w/ internal pull-up); VCC 3.3V; debounce in SW",
        "desc": "Manual override: rotate to select a device, press to toggle/confirm",
    },
    # --- deferred to a later phase (kept here so the agent knows it exists) ---
    "camera": {
        "kind": "sensor", "iface": "usb", "pin": None, "device": "/dev/video0",
        "model": "USB webcam (or CSI cam)", "enabled": False,
        "reads": ["frame"],
        "wiring": "USB (or CSI ribbon). NOT in v1.",
        "desc": "Optional visual context for the vision-aware variant — deferred",
    },
}

# --------------------------------------------------------------------------
# ACTUATORS
# --------------------------------------------------------------------------
ACTUATORS = {
    "fan": {
        "kind": "actuator", "iface": "h_bridge", "pin": None,
        "model": "DC motor via L293D half-bridge",
        "pins": {"en": 32, "in1": 35, "in2": 37},   # EN is PWM (speed); IN1/IN2 set direction
        "bcm": {"en": 12, "in1": 19, "in2": 26},
        "pwm_hz": 1000,
        "label": "Fan",
        "wiring": "L293D: EN1->pin 32 (PWM), IN1->35, IN2->37; motor on OUT1/OUT2; motor V+ from a separate 5-6V supply, common ground with the Jetson; logic Vcc 3.3-5V",
        "desc": "A real little DC fan/motor — spins (PWM speed) when NemoClaw decides to cool the desk. Low-voltage, safe on camera.",
    },
    "lamp": {
        "kind": "actuator", "iface": "digital_out", "pin": 16, "bcm": 23,
        "model": "mechanical relay ch1", "active_low": True,  # CONFIRM on bench
        "label": "Lamp",
        "wiring": "relay IN1 -> pin 16; module VCC 5V, GND common. No AC load — the relay click + onboard LED is the proof.",
        "desc": "Simulated desk lamp — relay clicks + onboard LED lights when ON",
    },
    "buzzer": {
        "kind": "actuator", "iface": "pwm", "pin": 33, "bcm": 13,
        "model": "5V passive buzzer", "pwm_hz": 2000,
        "label": "Buzzer",
        "wiring": "signal -> pin 33, GND common; passive buzzer needs a tone/PWM signal (not steady HIGH)",
        "desc": "Audio alerts (beeps / patterns)",
    },
    # optional 4th actuator — enable when the LED strip is wired to relay ch2
    "mood_light": {
        "kind": "actuator", "iface": "digital_out", "pin": 18, "bcm": 24,
        "model": "LED strip via mechanical relay ch2", "active_low": True, "enabled": False,
        "label": "Mood light",
        "wiring": "LED strip switched by relay IN2 -> pin 18; strip powered from its own supply, common ground. (If the strip turns out to be addressable WS2812, switch to an SPI MOSI drive instead.)",
        "desc": "Whole-strip on/off status light (green-ish idle / off / on for alert). Optional.",
    },
}

# I2C / SPI buses (reserved; nothing on them in v1 — BMP180 etc. would go on I2C-1).
BUSES = {
    "i2c-1": {"pins": (3, 5), "devices": {}},   # candidates: BMP180 (pressure), future ADS1115
}


def _enabled(spec):
    return spec.get("enabled", True)


def all_devices(include_disabled=False):
    """Flat {name: spec} of everything wired. Skips enabled=False devices unless asked."""
    merged = {}
    for name, spec in list(SENSORS.items()) + list(ACTUATORS.items()):
        if include_disabled or _enabled(spec):
            merged[name] = spec
    return merged


def sensors(include_disabled=False):
    return {k: v for k, v in all_devices(include_disabled).items() if v["kind"] == "sensor"}


def actuators(include_disabled=False):
    return {k: v for k, v in all_devices(include_disabled).items() if v["kind"] == "actuator"}
