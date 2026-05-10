"""Thin wrapper around Jetson.GPIO with a no-hardware fallback.

Everything hardware-facing goes through `gpio` (a module-level singleton):

    from src.hardware.board import gpio
    gpio.setup_in(11, pull="up")
    if gpio.read(11): ...
    pwm = gpio.pwm(33, hz=2000); pwm.start(50)

On a real Jetson this is `Jetson.GPIO` in BOARD mode. If Jetson.GPIO can't be
imported (running on a laptop / CI) or `COMPANION_SIMULATE=1` is set, it falls
back to a mock that logs calls and returns benign values — so `src/main.py`,
the PyQt5 dashboard, and the agent loop all run anywhere.

Py3.6-safe (the Jetson runs Python 3.6.9).
"""
import logging
import os
import threading

log = logging.getLogger("companion.board")

_FORCE_SIM = os.environ.get("COMPANION_SIMULATE", "").strip() not in ("", "0", "false", "False")


class _MockPWM(object):
    def __init__(self, pin, hz):
        self.pin, self.hz, self.duty, self.running = pin, hz, 0.0, False

    def start(self, duty):
        self.duty, self.running = float(duty), True
        log.debug("MOCK pwm start pin=%s hz=%s duty=%.1f", self.pin, self.hz, self.duty)

    def ChangeDutyCycle(self, duty):
        self.duty = float(duty)
        log.debug("MOCK pwm pin=%s duty=%.1f", self.pin, self.duty)

    def ChangeFrequency(self, hz):
        self.hz = float(hz)

    def stop(self):
        self.running = False
        log.debug("MOCK pwm stop pin=%s", self.pin)


class _Board(object):
    """Common surface over Jetson.GPIO; `real` tells you which backend is active."""

    def __init__(self):
        self._GPIO = None
        self.real = False
        self._lock = threading.RLock()
        self._states = {}      # pin -> last output value (mock bookkeeping)
        self._setup_done = False

        if not _FORCE_SIM:
            try:
                import warnings
                # Jetson.GPIO has no internal pull resistors; it warns on every setup()
                # with pull_up_down — silence the spam (we use external pull-ups; see
                # docs/hardware.md). We still pass the param so the code stays portable.
                warnings.filterwarnings("ignore", message=".*ignores setup.*pull_up_down.*")
                import Jetson.GPIO as GPIO  # type: ignore
                self._GPIO = GPIO
                self.real = True
            except Exception as e:  # ImportError, RuntimeError on non-Tegra, etc.
                log.warning("Jetson.GPIO unavailable (%s) — using the mock GPIO backend", e)
        else:
            log.info("COMPANION_SIMULATE set — using the mock GPIO backend")

    # -- lifecycle ---------------------------------------------------------
    def begin(self):
        with self._lock:
            if self._setup_done:
                return
            if self.real:
                self._GPIO.setmode(self._GPIO.BOARD)
                self._GPIO.setwarnings(False)
            self._setup_done = True
            log.info("GPIO backend: %s (BOARD mode)", "Jetson.GPIO" if self.real else "MOCK")

    def cleanup(self):
        with self._lock:
            if self.real and self._setup_done:
                try:
                    self._GPIO.cleanup()
                except Exception:
                    pass
            self._setup_done = False

    # -- pin config --------------------------------------------------------
    def setup_in(self, pin, pull=None):
        self.begin()
        if self.real:
            pud = self._GPIO.PUD_OFF
            if pull == "up":
                pud = self._GPIO.PUD_UP
            elif pull == "down":
                pud = self._GPIO.PUD_DOWN
            self._GPIO.setup(pin, self._GPIO.IN, pull_up_down=pud)
        else:
            self._states.setdefault(pin, 1 if pull == "up" else 0)

    def setup_out(self, pin, initial=0):
        self.begin()
        if self.real:
            self._GPIO.setup(pin, self._GPIO.OUT,
                             initial=self._GPIO.HIGH if initial else self._GPIO.LOW)
        else:
            self._states[pin] = 1 if initial else 0

    def set_direction(self, pin, mode, pull=None):
        """Re-purpose a pin between IN/OUT at runtime (used by the DHT bit-bang)."""
        if mode == "in":
            self.setup_in(pin, pull=pull)
        else:
            self.setup_out(pin, initial=1)

    # -- io ----------------------------------------------------------------
    def read(self, pin):
        if self.real:
            return int(self._GPIO.input(pin))
        return int(self._states.get(pin, 0))

    def write(self, pin, value):
        v = 1 if value else 0
        if self.real:
            self._GPIO.output(pin, self._GPIO.HIGH if v else self._GPIO.LOW)
        else:
            if self._states.get(pin) != v:
                log.debug("MOCK write pin=%s -> %s", pin, v)
        self._states[pin] = v

    def pwm(self, pin, hz):
        self.begin()
        if self.real:
            self._GPIO.setup(pin, self._GPIO.OUT)
            return self._GPIO.PWM(pin, hz)
        return _MockPWM(pin, hz)


# the one instance everyone imports
gpio = _Board()
