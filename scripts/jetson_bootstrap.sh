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

echo "==> apt packages (GPIO, I2C, SPI, PyQt5, build tools)"
# Package set for JetPack 4.6 / Ubuntu 18.04 (bionic). NOTE: no 'libgpiod2' here —
# that name only exists on Ubuntu 20.04+; bionic has libgpiod1/-dev, and Jetson.GPIO
# doesn't need libgpiod at all. We install adafruit-blinka's gpiod backend optionally.
APT_PKGS=(
    python3-pip python3-dev python3-setuptools
    python3-pyqt5
    i2c-tools python3-smbus
    libgpiod-dev python3-libgpiod gpiod
    git curl
)
sudo apt-get update -y
# Install as a group; if some package name is wrong on this release, fall back to
# installing them one at a time so one bad name doesn't block everything.
if ! sudo apt-get install -y "${APT_PKGS[@]}"; then
    echo "    (group install failed — retrying packages individually)"
    for p in "${APT_PKGS[@]}"; do
        sudo apt-get install -y "$p" || echo "    !! skipped apt package: $p"
    done
fi

echo "==> python pip deps (user install)"
python3 -m pip install --user --upgrade pip
# NOTE: the Adafruit CircuitPython / Blinka stack does NOT install on Python 3.6
# (build dep setuptools_scm needs 3.7+) — so we deliberately do NOT install it.
# Hardware layer = Jetson.GPIO (preinstalled) + python3-smbus (apt, above) + a
# small bit-bang DHT11 reader. Only light pure-Python extras here:
python3 -m pip install --user Jetson.GPIO || true        # no-op if already present
python3 -m pip install --user smbus2 requests python-telegram-bot || true

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
echo "        i2cdetect -y -r 1                 # lists I2C devices (e.g. BMP180 if wired)"
echo "        python3 -m src.main               # prints the registered hardware"
echo "    * Install NemoClaw:  curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"
echo "    * Autostart the dashboard later:  see systemd/companion-dashboard.service"
