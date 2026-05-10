"""Entry point for the IoT Desk Companion.

    python3 -m src.main

This is a skeleton — it wires the pieces together as they get built:

    1. load the pin map / hardware registry              (src.hardware.pins)        [done]
    2. bring up sensor readers + actuator drivers        (src.hardware.sensors/actuators)  [Phase 1/2]
    3. expose them as tools to NemoClaw, register pins,
       set the objective, run the agentic loop           (src.agent.*)              [Phase 2/4]
    4. start the PyQt5 kiosk dashboard on the HDMI screen (src.ui.dashboard)        [Phase 3]
    5. wire Telegram / NemoClaw-channel alerts            (src.notify.*)            [Phase 5]

For now it just prints the registered hardware so `deploy.ps1 -Run` does something
useful end-to-end (Windows -> Jetson -> runs -> prints).
"""
import sys

from src.hardware import pins


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    devices = pins.all_devices()
    sensors = {k: v for k, v in devices.items() if v["kind"] == "sensor"}
    actuators = {k: v for k, v in devices.items() if v["kind"] == "actuator"}

    print("Jetson Nano NeMo Claw IoT Desk Companion — skeleton")
    print("-" * 52)
    print("Sensors:")
    for name, spec in sensors.items():
        pin = spec.get("pin")
        print("  - {:<14} {:<11} pin={} model={}".format(
            name, spec["iface"], pin if pin is not None else "TBD", spec.get("model")))
    print("Actuators:")
    for name, spec in actuators.items():
        pin = spec.get("pin")
        print("  - {:<14} {:<11} pin={} model={}".format(
            name, spec["iface"], pin if pin is not None else "TBD", spec.get("model")))
    print("-" * 52)
    print("Next: wire the bench, fill in pins.py, then build src/hardware/sensors.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
