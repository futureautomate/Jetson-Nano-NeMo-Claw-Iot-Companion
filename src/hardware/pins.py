"""Single source of truth for the GPIO pin map.

Mirrors docs/hardware.md (synced to the Notion brief 2026-05-10). Pin numbers are
BOARD numbers (physical position on the Jetson Nano 40-pin header) — what
Jetson.GPIO uses after GPIO.setmode(GPIO.BOARD). BCM numbers are kept alongside
for reference. The Jetson Nano has no analog pins, so the MQ2 analog level is read
via an ADS1115 I2C ADC (channel A0, addr 0x48, on I2C-1 / pins 3+5).

Kept deliberately plain (dicts, py3.6-safe — no dataclasses) so the agent's
runtime hardware-registration path can build on the same structures.

Status: pins are LOCKED per the brief, but a few electrical details are still
"confirm on bench" — see the TODO list in docs/hardware.md.
"""

# kind:  "sensor" | "actuator"
# iface: "digital_in" | "digital_out" | "pwm" | "i2c_adc" | "spi" | "usb"
# pin:   BOARD pin number (or None for bus/USB devices)
# bcm:   BCM/GPIO number (reference only)
# model: concrete part (so DHT11 -> DHT22 is just a config change)

SENSORS = {
    "dht": {
        "kind": "sensor", "iface": "digital_in", "pin": 7, "bcm": 4,
        "model": "DHT11",  # swap to "DHT22" later — same wiring
        "reads": ["temperature_c", "humidity_pct"],
        "wiring": "1-wire data on pin 7; 4.7k pull-up to 3.3V on the data line",
        "desc": "Desk temperature & humidity",
    },
    "pir": {
        "kind": "sensor", "iface": "digital_in", "pin": 11, "bcm": 17,
        "model": "HC-SR501",
        "reads": ["motion"],
        "wiring": "OUT -> pin 11; module powered from 5V (verify OUT is <=3.3V); ~30-60s warm-up",
        "desc": "Desk occupancy / motion — HIGH = motion",
    },
    "mq2_digital": {
        "kind": "sensor", "iface": "digital_in", "pin": 13, "bcm": 27,
        "model": "MQ2",
        "reads": ["gas_threshold"],
        "wiring": "DO -> pin 13; trip point set by the pot on the MQ2 board; fast hardware trigger",
        "desc": "MQ2 comparator output — HIGH when gas/smoke crosses the threshold",
    },
    "mq2_analog": {
        "kind": "sensor", "iface": "i2c_adc", "pin": None,
        "model": "MQ2", "adc": {"chip": "ADS1115", "bus": 1, "addr": 0x48, "channel": 0},
        "reads": ["gas_level_raw", "gas_voltage"],
        "wiring": "AO -> ADS1115 ch A0; ADS1115 on I2C-1 (pins 3 SDA / 5 SCL), ADDR->GND; divider if AO swings to 5V",
        "desc": "Continuous smoke/LPG/methane/alcohol/H2 level for trend reasoning",
    },
    "encoder": {
        "kind": "sensor", "iface": "digital_in", "pin": None,
        "model": "incremental rotary encoder (M274)",
        "pins": {"a": 29, "b": 31, "sw": 33},  # BCM 5 / 6 / 13
        "bcm": {"a": 5, "b": 6, "sw": 13},
        "reads": ["delta", "button"],
        "wiring": "A->29, B->31, SW->33 (active-LOW, internal pull-up), VCC->3.3V; debounce in SW",
        "desc": "Manual override input — rotate to select a device, press to toggle",
    },
    "camera": {
        "kind": "sensor", "iface": "usb", "pin": None, "device": "/dev/video0",
        "model": "Logitech C270",
        "reads": ["frame"],
        "wiring": "USB",
        "desc": "Optional visual context for the vision-aware variant",
    },
}

ACTUATORS = {
    "relay_fan": {
        "kind": "actuator", "iface": "digital_out", "pin": 16, "bcm": 23,
        "model": "mechanical relay (ch1)", "active_low": True,  # CONFIRM on bench
        "label": "Fan",
        "wiring": "relay IN1 -> pin 16; VCC->5V; no AC load (relay click + onboard LED is the proof)",
        "desc": "Simulated fan — relay click + onboard LED indicate ON",
    },
    "relay_lamp": {
        "kind": "actuator", "iface": "digital_out", "pin": 18, "bcm": 24,
        "model": "mechanical relay (ch2)", "active_low": True,  # CONFIRM on bench
        "label": "Lamp",
        "wiring": "relay IN2 -> pin 18; VCC->5V; no AC load",
        "desc": "Simulated desk lamp — relay click + onboard LED indicate ON",
    },
    "led_strip": {
        "kind": "actuator", "iface": "spi", "pin": 19, "bcm": 10,  # SPI0 MOSI
        "model": "WS2812 strip",
        "lib": "adafruit-circuitpython-neopixel-spi",  # NOT rpi_ws281x on Jetson; see docs/hardware.md
        "label": "Status light",
        "wiring": "WS2812 DIN <- SPI0 MOSI (pin 19); 5V from EXTERNAL supply (not Jetson 5V rail); common ground; enable SPI0 via jetson-io",
        "desc": "Ambient / mood light: green = idle, amber = warning, red = alert",
    },
    "buzzer": {
        "kind": "actuator", "iface": "pwm", "pin": 22, "bcm": 25,
        "model": "passive buzzer",
        "label": "Buzzer",
        "wiring": "signal -> pin 22, GND->GND; passive buzzer needs a tone/PWM signal, not steady HIGH/LOW",
        "desc": "Audio alerts",
    },
}

# Buses currently in use (informational; see docs/hardware.md).
BUSES = {
    "i2c-1": {"pins": (3, 5), "devices": {"ADS1115": 0x48}},
    "spi0":  {"pins": (19, 23, 24), "uses": "WS2812 LED strip on MOSI (pin 19)"},
}


def all_devices():
    """Flat {name: spec} of everything wired, sensors + actuators."""
    merged = {}
    merged.update(SENSORS)
    merged.update(ACTUATORS)
    return merged
