"""Sensor readers for the v1 build — all digital, via Jetson.GPIO.

Wired per src/hardware/pins.py / docs/hardware.md:
    DHT11   pin 7   (1-wire, bit-banged)        -> temperature_c, humidity_pct
    PIR     pin 11  (digital)                    -> motion (bool)
    MQ2     pin 13  (digital threshold / DO)     -> gas_alarm (bool)
    sound   pin 15  (digital threshold / DO)     -> sound_alarm (bool)  [latched briefly]
    LDR     pin 22  (digital threshold / DO)     -> is_dark (bool)
    encoder pins 29/31/36 (A/B/SW)               -> delta (int), button (bool)

`Sensors().read_all()` returns a flat dict suitable for handing to NemoClaw as
tool results / showing on the dashboard. Works with or without real hardware
(see src.hardware.board).
"""
import logging
import time

from src.hardware.board import gpio
from src.hardware import pins

log = logging.getLogger("companion.sensors")


# --------------------------------------------------------------------------
# DHT11 — bit-banged 1-wire read.
# Reads are timing-sensitive and pure Python on Linux is jittery, so we retry.
# If this proves too flaky on the Nano, the fallback is an Arduino Mini reading
# the DHT and reporting over USB serial (we have Arduinos in inventory).
# --------------------------------------------------------------------------
def read_dht11(pin, retries=15, settle_s=2.0):
    """Return (temperature_c, humidity_pct) as ints, or None if all retries fail."""
    last_err = None
    for attempt in range(retries):
        try:
            return _dht11_once(pin)
        except Exception as e:  # checksum / framing / timing
            last_err = e
            time.sleep(0.12)
    log.debug("DHT11 on pin %s: %d/%d reads failed (last: %s)", pin, retries, retries, last_err)
    return None


def _dht11_once(pin):
    # --- start signal: pull low >18ms, then release ---
    gpio.set_direction(pin, "out")
    gpio.write(pin, 1)
    time.sleep(0.05)
    gpio.write(pin, 0)
    time.sleep(0.02)            # >= 18 ms low
    gpio.set_direction(pin, "in", pull="up")

    # --- sample the line as fast as we can; decode by run-length ---
    samples = []
    # cap iterations so a dead/disconnected sensor can't spin forever
    for _ in range(10000):
        samples.append(gpio.read(pin))
    # collapse to (value, run_length) pairs
    runs = []
    cur = samples[0]
    n = 0
    for s in samples:
        if s == cur:
            n += 1
        else:
            runs.append((cur, n))
            cur, n = s, 1
    runs.append((cur, n))

    # The frame: [initial HIGH idle] LOW(80us) HIGH(80us) then 40 x { LOW(50us) HIGH(26-28us=0 | 70us=1) }
    # We look for the 80us HIGH response pulse, then take the HIGH runs after each LOW.
    # Find the first 1-run that is clearly longer than typical noise -> response pulse.
    high_runs = [length for (val, length) in runs if val == 1]
    if len(high_runs) < 42:
        raise ValueError("not enough pulses (%d)" % len(high_runs))
    # drop the leading idle + the ~80us response high, keep the 40 data highs
    data_highs = high_runs[-40:]
    threshold = (max(data_highs) + min(data_highs)) / 2.0
    bits = [1 if h > threshold else 0 for h in data_highs]

    by = [0, 0, 0, 0, 0]
    for i, b in enumerate(bits):
        by[i // 8] = (by[i // 8] << 1) | b
    hum_int, hum_dec, tmp_int, tmp_dec, chk = by
    if ((hum_int + hum_dec + tmp_int + tmp_dec) & 0xFF) != chk:
        raise ValueError("checksum mismatch")
    if hum_int == 0 and tmp_int == 0:
        raise ValueError("all-zero frame")
    return tmp_int, hum_int   # DHT11: decimals are ~always 0; ints are temp(C)/RH(%)


# --------------------------------------------------------------------------
# Rotary encoder — poll-based quadrature decode + push button.
# --------------------------------------------------------------------------
class Encoder(object):
    def __init__(self, pin_a, pin_b, pin_sw):
        self.pin_a, self.pin_b, self.pin_sw = pin_a, pin_b, pin_sw
        gpio.setup_in(pin_a, pull="up")
        gpio.setup_in(pin_b, pull="up")
        gpio.setup_in(pin_sw, pull="up")
        self._last_ab = (gpio.read(pin_a) << 1) | gpio.read(pin_b)
        self._accum = 0          # accumulated detents since last read
        self._last_sw = 1
        self._sw_edge_t = 0.0
        # gray-code transition table: (prev<<2 | cur) -> +1 / -1 / 0
        self._table = {0b0001: +1, 0b0111: +1, 0b1110: +1, 0b1000: +1,
                       0b0010: -1, 0b1011: -1, 0b1101: -1, 0b0100: -1}

    def poll(self):
        """Call frequently. Returns (delta_detents, button_pressed_edge)."""
        a, b = gpio.read(self.pin_a), gpio.read(self.pin_b)
        ab = (a << 1) | b
        step = self._table.get((self._last_ab << 2) | ab, 0)
        self._last_ab = ab
        self._accum += step
        delta, self._accum = self._accum // 4, self._accum % 4   # 4 quadrature steps per detent

        sw = gpio.read(self.pin_sw)
        pressed = False
        now = time.time()
        if sw == 0 and self._last_sw == 1 and (now - self._sw_edge_t) > 0.05:  # falling edge + debounce
            pressed = True
            self._sw_edge_t = now
        self._last_sw = sw
        return delta, pressed


# --------------------------------------------------------------------------
# The whole sensor set.
# --------------------------------------------------------------------------
class Sensors(object):
    """Owns pin setup for all v1 sensors; `read_all()` snapshots them."""

    def __init__(self, dht_min_interval_s=2.5, sound_latch_s=2.0):
        s = pins.SENSORS
        self._dht_pin = s["dht"]["pin"]
        self._pir_pin = s["pir"]["pin"]
        self._mq2_pin = s["mq2"]["pin"]
        self._snd_pin = s["sound"]["pin"]
        self._ldr_pin = s["ldr"]["pin"]
        self._ldr_active_low = s["ldr"].get("active_low", True)

        gpio.setup_in(self._pir_pin)
        gpio.setup_in(self._mq2_pin)
        gpio.setup_in(self._snd_pin)
        gpio.setup_in(self._ldr_pin)
        # DHT pin is reconfigured IN/OUT on each read.

        ep = s["encoder"]["pins"]
        self.encoder = Encoder(ep["a"], ep["b"], ep["sw"])

        self._dht_min_interval = dht_min_interval_s
        self._dht_last_t = 0.0
        self._dht_cache = None          # (temp_c, hum_pct)
        self._sound_latch_s = sound_latch_s
        self._sound_last_hit_t = 0.0

    # individual reads -----------------------------------------------------
    def motion(self):
        return bool(gpio.read(self._pir_pin))

    def gas_alarm(self):
        return bool(gpio.read(self._mq2_pin))

    def sound_alarm(self):
        if gpio.read(self._snd_pin):
            self._sound_last_hit_t = time.time()
        return (time.time() - self._sound_last_hit_t) <= self._sound_latch_s

    def is_dark(self):
        v = gpio.read(self._ldr_pin)
        return (v == 0) if self._ldr_active_low else (v == 1)

    def dht(self):
        """Cached temp/humidity — re-reads at most every dht_min_interval_s (DHT11 limit)."""
        now = time.time()
        if (now - self._dht_last_t) >= self._dht_min_interval or self._dht_cache is None:
            self._dht_last_t = now
            val = read_dht11(self._dht_pin)
            if val is not None:
                self._dht_cache = val
        return self._dht_cache

    def encoder_poll(self):
        return self.encoder.poll()

    # snapshot -------------------------------------------------------------
    def read_all(self):
        temp = hum = None
        d = self.dht()
        if d is not None:
            temp, hum = d
        delta, pressed = self.encoder.poll()
        return {
            "temperature_c": temp,
            "humidity_pct": hum,
            "motion": self.motion(),
            "gas_alarm": self.gas_alarm(),
            "sound_alarm": self.sound_alarm(),
            "is_dark": self.is_dark(),
            "encoder_delta": delta,
            "encoder_pressed": pressed,
            "ts": time.time(),
        }
