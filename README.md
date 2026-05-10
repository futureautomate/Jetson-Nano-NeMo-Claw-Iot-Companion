# 🤖 Jetson Nano NeMo Claw IoT Desk Companion

Multi-sensor / multi-actuator agentic desk companion running on an **NVIDIA Jetson Nano**, driven by **NVIDIA NemoClaw** (OpenClaw + OpenShell runtime). You tell the agent what each GPIO pin does at runtime, give it a high-level objective ("keep the desk safe and comfortable, alert me on gas or smoke"), and it reads every sensor, reasons across them, and triggers the right actuators — with a PyQt5 dashboard on a 4.3" DWIN **HDMI** touch screen showing the live reasoning log, and a rotary encoder for manual override.

Full project brief lives in Notion → *Future Automation — Mission Control › Project Tracker*.

---

## Hardware (summary — see [docs/hardware.md](docs/hardware.md) for the authoritative pin map)

| Class | Device | Notes |
|---|---|---|
| Sensor | DHT11 (→ DHT22 later) | temp + humidity, digital |
| Sensor | PIR motion | desk occupancy, digital |
| Sensor | MQ2 gas/smoke | **analog** → needs an ADS1115 ADC over I²C (Jetson has no analog pins) |
| Sensor | Rotary encoder | manual override input |
| Sensor | Logitech C270 webcam | optional visual context (USB) |
| Actuator | 4-ch relay (Fan / Lamp) | no AC loads — relay click + onboard LED is the on-camera proof |
| Actuator | LED strip | status / mood light |
| Actuator | Passive buzzer | audio alerts |
| Display | DWIN 4.3" HDMI capacitive touch | HDMI for video, USB for touch; runs the PyQt5 dashboard |

---

## Where things run

- **This repo (Windows, `d:\Projects\Jetson-Nano-NeMo-Claw-Iot-Companion`)** — source of truth. All code is authored here and pushed to GitHub.
- **GitHub** — `git@github-work:futureautomate/Jetson-Nano-NeMo-Claw-Iot-Companion.git` (public; **work** account `futureautomate`).
- **Jetson Nano** — runs the actual thing: GPIO, HDMI dashboard, camera, and the NemoClaw sandbox. Reached over SSH as host `jetson` (`192.168.0.74`). Code lives at `~/jetson-companion/`.

```
Windows (author)                         Jetson Nano (~/jetson-companion)
────────────────                         ────────────────────────────────
 edit code  ── git push (github-work) ─► GitHub (history / backup, public)
     │
     └──────── ./deploy.ps1 ───────────► rsync/tar over SSH ──► python3 -m src.main
                (fast inner loop)                                (GPIO • HDMI UI • NemoClaw)
       ◄──────── ssh jetson '…' (run / tail logs / test) ────────
```

**Sync model:** one-way, Windows → Jetson. The Jetson copy is a *mirror* of the repo plus a separate untracked `~/jetson-companion-data/` for runtime state (logs, sqlite, secrets). Git is used for version history and backup; `deploy.ps1` is used for the edit→test loop so you don't have to commit every iteration. (You *can* instead `git clone` the public repo on the Jetson and `git pull` — see below — but `deploy` is faster while iterating.)

### Deploy to the Jetson

```powershell
# from the repo root, on Windows:
./deploy.ps1            # rsync (via WSL) if available, else tar-over-SSH; mirrors repo → jetson:~/jetson-companion
./deploy.ps1 -Run       # ...then launch  python3 -m src.main  on the Jetson
./deploy.ps1 -Clean     # wipe ~/jetson-companion first (handles deleted files)
```

```bash
# equivalent from Git Bash / WSL / macOS:
./deploy.sh
```

### Run / inspect on the Jetson

```bash
ssh jetson 'cd ~/jetson-companion && python3 -m src.main'
ssh jetson 'tail -f ~/jetson-companion-data/companion.log'
ssh jetson 'systemctl --user status companion-dashboard'   # once the service is installed
```

### Alternative: git on the device (instead of deploy.ps1)

The repo is public, so the Jetson can pull read-only with no key setup:

```bash
ssh jetson 'git clone https://github.com/futureautomate/Jetson-Nano-NeMo-Claw-Iot-Companion.git ~/jetson-companion'
# later:
ssh jetson 'cd ~/jetson-companion && git pull'
```

Pick one or the other for `~/jetson-companion` — don't mix a git clone with `deploy.ps1 -Clean`.

---

## First-time Jetson setup

```bash
# 1. get the code there (either deploy.ps1 from Windows, or git clone above)
# 2. install OS + Python deps, GPIO permissions, autostart:
ssh jetson 'cd ~/jetson-companion && bash scripts/jetson_bootstrap.sh'
# 3. install NemoClaw (one-line installer; runs as the normal user, no sudo):
ssh jetson 'curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash'
#    then run its onboarding wizard and pick an inference provider (TBD).
```

Jetson facts to keep in mind: JetPack 4.6.x (L4T R32.7.6), `aarch64`, **system Python is 3.6.9** (NemoClaw / modern SDKs may need a newer Python — handled in `jetson_bootstrap.sh` / a venv / Docker; Docker is already installed), 4 GB RAM (local LLMs are not realistic — NemoClaw routes to a cloud provider).

---

## Repo layout

```
.
├── deploy.ps1 / deploy.sh        # Windows → Jetson sync
├── docs/hardware.md              # authoritative pin map + wiring notes
├── scripts/jetson_bootstrap.sh   # one-shot device setup
├── systemd/companion-dashboard.service
├── src/
│   ├── main.py                   # entry point — wires UI + agent loop together
│   ├── hardware/pins.py          # single source of truth for the GPIO pin map
│   ├── hardware/                 # sensors.py, actuators.py        (Phase 1/2)
│   ├── agent/                    # tool defs + NemoClaw objective loop (Phase 2/4)
│   ├── ui/                       # PyQt5 480×800 kiosk dashboard     (Phase 3)
│   └── notify/                   # Telegram alerts (or NemoClaw channels)
└── requirements.txt
```

## Build phases (mirrors the Notion tracker)

1. Hardware wiring (incl. ADS1115 for the MQ2 analog line)
2. NemoClaw install + register sensor/actuator tools
3. PyQt5 HDMI dashboard (kiosk, autostart)
4. Agentic loop — runtime pin registration, objective setting, multi-sensor cross-reasoning
5. Testing + polish (24 h soak, Telegram, override)
6. 3D-printed enclosure

> ⚠️ Known doc fixes in progress: DHT11 vs DHT22 / MQ2 vs MQ-135 naming, and "analog pins A0–A2" — the Jetson has no ADC, so the MQ2 analog reading goes through an ADS1115 on I²C. `docs/hardware.md` reflects the corrected wiring.
