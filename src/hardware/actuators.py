"""Actuator drivers for the v1 build — via Jetson.GPIO.

Wired per src/hardware/pins.py / docs/hardware.md:
    fan        L293D EN1=32 (PWM speed), IN1=35, IN2=37   -> a real little DC motor that spins
    lamp       relay ch1 = pin 16 (active-LOW, confirm)   -> relay click + onboard LED
    buzzer     pin 33 (passive — needs a tone/PWM signal)
    mood_light relay ch2 = pin 18 (optional, disabled until the LED strip is wired)

`Actuators` owns pin setup; methods are safe to call from the agent loop or the
dashboard. Works with or without real hardware (see src.hardware.board).
"""
import logging
import threading
import time

from src.hardware.board import gpio
from src.hardware import pins

log = logging.getLogger("companion.actuators")


def _relay_levels(active_low):
    return (0, 1) if active_low else (1, 0)   # (on_level, off_level)


class _Relay(object):
    def __init__(self, pin, active_low=True):
        self.pin, self.active_low = pin, active_low
        self._on_lvl, self._off_lvl = _relay_levels(active_low)
        gpio.setup_out(pin, initial=self._off_lvl)
        self._on = False

    def on(self):
        gpio.write(self.pin, self._on_lvl); self._on = True

    def off(self):
        gpio.write(self.pin, self._off_lvl); self._on = False

    def set(self, state):
        self.on() if state else self.off()

    @property
    def is_on(self):
        return self._on


class _Fan(object):
    """DC motor through an L293D half-bridge: EN = PWM (speed), IN1/IN2 = direction."""

    def __init__(self, en_pin, in1_pin, in2_pin, pwm_hz=1000):
        self.en_pin, self.in1_pin, self.in2_pin = en_pin, in1_pin, in2_pin
        gpio.setup_out(in1_pin, initial=0)
        gpio.setup_out(in2_pin, initial=0)
        self._pwm = gpio.pwm(en_pin, pwm_hz)
        self._pwm.start(0)
        self._speed = 0

    def set_speed(self, pct):
        """0..100. 0 = stopped (motor coasts)."""
        pct = max(0, min(100, int(round(pct))))
        if pct > 0:
            gpio.write(self.in1_pin, 1)   # one direction is enough for a fan
            gpio.write(self.in2_pin, 0)
        else:
            gpio.write(self.in1_pin, 0)
            gpio.write(self.in2_pin, 0)
        self._pwm.ChangeDutyCycle(pct)
        self._speed = pct
        log.debug("fan speed -> %d%%", pct)

    def off(self):
        self.set_speed(0)

    @property
    def speed(self):
        return self._speed

    def stop(self):
        try:
            self._pwm.stop()
        except Exception:
            pass


class _Buzzer(object):
    """Passive buzzer driven with PWM (a square-wave 'tone')."""

    def __init__(self, pin, default_hz=2000):
        self.pin, self.default_hz = pin, default_hz
        self._pwm = gpio.pwm(pin, default_hz)
        self._pwm.start(0)        # 0% duty = silent
        self._lock = threading.Lock()

    def _tone(self, hz, on):
        with self._lock:
            if on:
                self._pwm.ChangeFrequency(max(50, int(hz)))
                self._pwm.ChangeDutyCycle(50)
            else:
                self._pwm.ChangeDutyCycle(0)

    def beep(self, duration_s=0.15, hz=None, blocking=False):
        hz = hz or self.default_hz
        if not blocking:
            threading.Thread(target=self._beep_blocking, args=(duration_s, hz), daemon=True).start()
        else:
            self._beep_blocking(duration_s, hz)

    def _beep_blocking(self, duration_s, hz):
        self._tone(hz, True)
        time.sleep(duration_s)
        self._tone(hz, False)

    def pattern(self, beeps=2, on_s=0.12, off_s=0.10, hz=None, blocking=False):
        hz = hz or self.default_hz
        def run():
            for i in range(beeps):
                self._beep_blocking(on_s, hz)
                if i < beeps - 1:
                    time.sleep(off_s)
        (run() if blocking else threading.Thread(target=run, daemon=True).start())

    def alert(self):
        """Distinctive 3-pulse rising alert (gas/smoke etc.)."""
        def run():
            for hz in (1500, 2200, 3000):
                self._beep_blocking(0.18, hz)
                time.sleep(0.06)
        threading.Thread(target=run, daemon=True).start()

    def off(self):
        self._tone(self.default_hz, False)

    def stop(self):
        try:
            self._pwm.stop()
        except Exception:
            pass


class Actuators(object):
    def __init__(self):
        a = pins.ACTUATORS
        fp = a["fan"]["pins"]
        self.fan = _Fan(fp["en"], fp["in1"], fp["in2"], pwm_hz=a["fan"].get("pwm_hz", 1000))
        self.lamp = _Relay(a["lamp"]["pin"], active_low=a["lamp"].get("active_low", True))
        self.buzzer = _Buzzer(a["buzzer"]["pin"], default_hz=a["buzzer"].get("pwm_hz", 2000))
        self.mood_light = None
        ml = a.get("mood_light")
        if ml and ml.get("enabled", False):
            self.mood_light = _Relay(ml["pin"], active_low=ml.get("active_low", True))

    # convenience -----------------------------------------------------------
    def fan_set(self, speed_pct):
        self.fan.set_speed(speed_pct)

    def lamp_on(self):
        self.lamp.on()

    def lamp_off(self):
        self.lamp.off()

    def buzz(self, duration_s=0.15, hz=None):
        self.buzzer.beep(duration_s, hz)

    def alert(self):
        self.buzzer.alert()

    def state(self):
        st = {
            "fan_speed": self.fan.speed,
            "lamp": self.lamp.is_on,
            "buzzer": False,  # momentary; not tracked as a steady state
        }
        if self.mood_light is not None:
            st["mood_light"] = self.mood_light.is_on
        return st

    def all_off(self):
        self.fan.off()
        self.lamp.off()
        self.buzzer.off()
        if self.mood_light is not None:
            self.mood_light.off()

    def shutdown(self):
        self.all_off()
        self.fan.stop()
        self.buzzer.stop()
