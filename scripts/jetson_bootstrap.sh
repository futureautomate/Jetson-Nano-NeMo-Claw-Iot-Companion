#!/usr/bin/env bash
# One-shot device setup for the Jetson Nano side of the IoT Desk Companion.
# Run it FROM the deployed repo on the Jetson:
#
#     ssh jetson 'cd ~/jetson-companion && bash scripts/jetson_bootstrap.sh'
#
# Safe to re-run. It does NOT install NemoClaw — do that separately:
#     curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
set -euo pipefail

echo "==> Jetson bootstrap — $(uname -m), $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unknown}")"
[ -f /etc/nv_tegra_release ] && echo "    $(cat /etc/nv_tegra_release)"
echo "    python3: $(python3 --version 2>&1)"

DATA_DIR="${HOME}/jetson-companion-data"
mkdir -p "$DATA_DIR"
echo "==> runtime data dir: $DATA_DIR"

echo "==> apt packages (GPIO, I2C, PyQt5, build tools)"
sudo apt-get update -y
sudo apt-get install -y \
    python3-pip python3-dev python3-setuptools \
    python3-pyqt5 \
    i2c-tools python3-smbus \
    libgpiod2 \
    git curl

echo "==> python pip deps (user install)"
python3 -m pip install --user --upgrade pip
# Jetson.GPIO is usually preinstalled on JetPack; install/upgrade just in case.
python3 -m pip install --user Jetson.GPIO || true
# ADS1115 (MQ2 analog). adafruit-blinka support for py3.6 is iffy — don't hard-fail.
python3 -m pip install --user adafruit-circuitpython-ads1x15 adafruit-blinka || \
    echo "    !! adafruit libs failed on this Python — revisit (venv / Docker / py3.8+)."
python3 -m pip install --user requests python-telegram-bot || true

echo "==> GPIO / I2C permissions for user '$USER'"
sudo groupadd -f gpio
sudo usermod -aG gpio,i2c,video,dialout "$USER" || true
# Udev rule so /dev/gpiochip* is group-writable (JetPack ships one, this is a backup).
echo 'SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"' | sudo tee /etc/udev/rules.d/99-gpio.rules >/dev/null
sudo udevadm control --reload-rules || true

echo
echo "==> Done. Notes:"
echo "    * Log out / back in (or reboot) for the new groups to take effect."
echo "    * Quick checks:"
echo "        i2cdetect -y -r 1                 # should show 0x48 once the ADS1115 is wired"
echo "        python3 -m src.main               # prints the registered hardware"
echo "    * Install NemoClaw:  curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"
echo "    * Autostart the dashboard later:  see systemd/companion-dashboard.service"
