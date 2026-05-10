"""Entry point for the IoT Desk Companion.

    python3 -m src.main              # print the registered hardware (pin map)
    python3 -m src.main --selftest   # bring up GPIO, exercise every actuator, read every sensor once
    python3 -m src.main --monitor    # loop: print all sensor readings once a second (Ctrl+C to stop)

Runs anywhere: on the Jetson it uses Jetson.GPIO; on a laptop / CI (or with
COMPANION_SIMULATE=1) it uses a mock GPIO backend, so nothing here crashes.

Still to come (mirrors the Notion phases): NemoClaw tool registration + objective
loop (src/agent/*), the PyQt5 HDMI dashboard (src/ui/*), Telegram alerts (src/notify/*).
"""
import argparse
import logging
import sys
import time

from src.hardware import pins
from src.hardware.board import gpio


def _print_hardware():
    print("Jetson Nano NeMo Claw IoT Desk Companion — v1 hardware registry")
    print("-" * 62)
    print("GPIO backend:", "Jetson.GPIO (real)" if gpio.real else "MOCK (no hardware)")
    print("\nSensors:")
    for name, spec in pins.sensors().items():
        pin = spec.get("pin")
        pin_s = pin if pin is not None else ("/".join(str(v) for v in spec.get("pins", {}).values()) or "—")
        print("  {:<10} {:<12} pin {:<8} {}".format(name, spec["iface"], pin_s, spec.get("desc", "")))
    print("\nActuators:")
    for name, spec in pins.actuators().items():
        pin = spec.get("pin")
        pin_s = pin if pin is not None else ("/".join(str(v) for v in spec.get("pins", {}).values()) or "—")
        print("  {:<10} {:<12} pin {:<8} {}".format(name, spec["iface"], pin_s, spec.get("desc", "")))
    disabled = [n for n, s in pins.all_devices(include_disabled=True).items() if not s.get("enabled", True)]
    if disabled:
        print("\nDisabled (deferred / not wired):", ", ".join(disabled))
    print("-" * 62)


def _selftest():
    from src.hardware.sensors import Sensors
    from src.hardware.actuators import Actuators
    print("== SELFTEST ==  backend:", "Jetson.GPIO" if gpio.real else "MOCK")
    if not gpio.real:
        print("(mock backend — actuator effects are logged, sensor reads are placeholders)")
    sensors = Sensors()
    act = Actuators()
    try:
        print("\n-- actuators --")
        print("lamp ON ...");  act.lamp_on();  time.sleep(0.6)
        print("lamp OFF ..."); act.lamp_off(); time.sleep(0.3)
        for s in (30, 60, 100, 0):
            print("fan -> %d%%" % s); act.fan_set(s); time.sleep(0.6)
        print("buzzer beep ..."); act.buzz(0.15); time.sleep(0.4)
        print("buzzer alert pattern ..."); act.alert(); time.sleep(1.2)
        if act.mood_light is not None:
            print("mood light ON/OFF ..."); act.mood_light.on(); time.sleep(0.4); act.mood_light.off()

        print("\n-- sensors (3 quick reads) --")
        for i in range(3):
            print("  ", sensors.read_all())
            time.sleep(0.5)
        print("\nactuator state:", act.state())
        print("\nSELFTEST OK")
        return 0
    finally:
        act.shutdown()
        gpio.cleanup()


def _monitor(period_s=1.0):
    from src.hardware.sensors import Sensors
    print("== MONITOR ==  backend:", "Jetson.GPIO" if gpio.real else "MOCK", " (Ctrl+C to stop)")
    sensors = Sensors()
    try:
        while True:
            r = sensors.read_all()
            print("T={t}C  RH={h}%  motion={m}  gas={g}  sound={s}  dark={d}  enc(d={ed},btn={eb})".format(
                t=r["temperature_c"], h=r["humidity_pct"], m=int(r["motion"]), g=int(r["gas_alarm"]),
                s=int(r["sound_alarm"]), d=int(r["is_dark"]), ed=r["encoder_delta"], eb=int(r["encoder_pressed"])))
            time.sleep(period_s)
    except KeyboardInterrupt:
        pass
    finally:
        gpio.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="src.main", description="IoT Desk Companion")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--selftest", action="store_true", help="exercise every actuator + read every sensor once")
    g.add_argument("--monitor", action="store_true", help="loop printing all sensor readings")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.selftest:
        return _selftest()
    if args.monitor:
        _monitor()
        return 0
    _print_hardware()
    print("\nNext: wire the bench (see docs/hardware.md), then `python3 -m src.main --selftest`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
