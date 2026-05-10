"""Single source of truth for the GPIO pin map.

Mirrors docs/hardware.md. Pin numbers are BOARD numbers (physical 40-pin header),
i.e. what Jetson.GPIO uses after GPIO.setmode(GPIO.BOARD). All values are TBD
placeholders until the wiring is finalized on the bench — update both this file
and docs/hardware.md together.

Kept deliberately plain (dicts, py3.6-safe — no dataclasses) so the agent's
runtime hardware-registration path can build on the same structures.
"""

# --- Devices the agent can be told about at runtime ------------------------
# kind: one of "sensor" / "actuator"
# iface: how it connects -- "digital_in" / "digital_out" / "pwm" / "i2c_adc" / "usb"
# pin:   BOARD pin number, or None for bus/USB devices
# model: concrete part (so e.g. DHT11 -> DHT22 is just a config change)

SENSORS = {
    "dht": {
        "kind": "sensor", "iface": "digital_in", "pin": None,  # e.g. 7
        "model": "DHT11",  # swap to "DHT22" later
        "reads": ["temperature_c", "humidity_pct"],
        "desc": "Desk temperature & humidity",
    },
    "pir": {
        "kind": "sensor", "iface": "digital_in", "pin": None,  # e.g. 11
        "model": "HC-SR501",
        "reads": ["motion"],
        "desc": "Desk occupancy / motion (HIGH = motion). ~30-60s warm-up.",
    },
    "mq2_analog": {
        "kind": "sensor", "iface": "i2c_adc", "pin": None,  # ADS1115 channel A0
        "model": "MQ2", "adc": {"chip": "ADS1115", "addr": 0x48, "channel": 0},
        "reads": ["gas_level_raw", "gas_voltage"],
        "desc": "Smoke / LPG / methane / alcohol / H2 — analog level via ADS1115.",
    },
    "mq2_digital": {
        "kind": "sensor", "iface": "digital_in", "pin": None,  # optional, e.g. 13
        "model": "MQ2",
        "reads": ["gas_threshold"],
        "desc": "MQ2 comparator output (trip point set by the module's pot).",
    },
    "encoder": {
        "kind": "sensor", "iface": "digital_in", "pin": None,  # A/B/SW e.g. 16/18/22
        "model": "incremental rotary encoder",
        "pins": {"a": None, "b": None, "sw": None},
        "reads": ["delta", "button"],
        "desc": "Manual override input (rotate to select device, press to toggle).",
    },
    "camera": {
        "kind": "sensor", "iface": "usb", "pin": None, "device": "/dev/video0",
        "model": "Logitech C270",
        "reads": ["frame"],
        "desc": "Optional visual context for the vision-aware variant.",
    },
}

ACTUATORS = {
    "relay_fan": {
        "kind": "actuator", "iface": "digital_out", "pin": None,  # e.g. 29
        "model": "mechanical relay (ch1)", "active_low": True,  # CONFIRM on bench
        "label": "Fan",
        "desc": "Simulated fan — relay click + onboard LED indicate ON. No AC load.",
    },
    "relay_lamp": {
        "kind": "actuator", "iface": "digital_out", "pin": None,  # e.g. 31
        "model": "mechanical relay (ch2)", "active_low": True,  # CONFIRM on bench
        "label": "Lamp",
        "desc": "Simulated desk lamp — relay click + onboard LED indicate ON. No AC load.",
    },
    "led_strip": {
        "kind": "actuator", "iface": "pwm", "pin": None,  # e.g. 33
        "model": "LED strip", "addressable": None,  # decide: WS2812 vs plain 12V
        "label": "Status light",
        "desc": "Ambient / mood light: green = idle, amber = warning, red = alert.",
    },
    "buzzer": {
        "kind": "actuator", "iface": "pwm", "pin": None,  # e.g. 32 (needs tone/PWM)
        "model": "passive buzzer",
        "label": "Buzzer",
        "desc": "Audio alerts (passive buzzer — needs a PWM/tone signal, not HIGH/LOW).",
    },
}

# I2C / other buses currently in use (informational; see docs/hardware.md).
BUSES = {
    "i2c-1": {"pins": (3, 5), "devices": {"ADS1115": 0x48}},
}


def all_devices():
    """Flat {name: spec} of everything wired, sensors + actuators."""
    merged = {}
    merged.update(SENSORS)
    merged.update(ACTUATORS)
    return merged
