# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RaspiZeroCam is a standalone, headless camera streaming server for Raspberry Pi Zero 2 W. It provides RTSP/WebRTC/HLS video streams via hardware H.264 encoding, a REST API, WiFi config portal, and AP fallback. The video stack is handled by mediamtx; FastAPI handles config/status/WiFi/UI only.

**Target hardware:** Pi Zero 2 W + Camera Module 3 (imx708)
**First use-case:** Rear-view camera for the MyLevo e-bike app (D:\Development\myLevo)

Phase 1 (MJPEG via picamera2 on Pi Zero W v1.1) has been fully replaced by Phase 2 (mediamtx + H.264 on Pi Zero 2 W). The design spec is in `docs/superpowers/specs/2026-04-11-phase2-design.md`.

## Build & Test Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_mediamtx.py -v

# Run a specific test
python -m pytest tests/test_api.py::test_get_status -v

# Verify Python syntax (no hardware needed)
python -c "import ast; ast.parse(open('app/main.py').read()); print('OK')"
```

No local dev server — the app integrates with mediamtx and libcamera, which require Raspberry Pi hardware. Development happens on Windows, tests run on Windows without the Pi, deployment via git on the Pi.

## Deployment

```bash
# Deploy to Pi (from Windows)
ssh raspizerocam "cd ~/RaspiZeroCam && git pull && sudo cp -r app /opt/raspizerocam/ && sudo systemctl restart raspizerocam"

# Regenerate mediamtx.yml from current AppConfig and restart mediamtx
ssh raspizerocam "sudo /opt/raspizerocam/venv/bin/python -c 'from app.config import AppConfig; from app.mediamtx import generate_yaml; open(\"/opt/raspizerocam/mediamtx.yml\",\"w\").write(generate_yaml(AppConfig()))' && sudo systemctl restart mediamtx"

# View logs
ssh raspizerocam "journalctl -u mediamtx -u raspizerocam -f"

# First-time install on Pi (fresh OS)
ssh raspizerocam "git clone https://github.com/andreasschegg/RaspiZeroCam.git && cd RaspiZeroCam && sudo ./install.sh"
```

No Docker — runs directly on Raspberry Pi OS Lite Bookworm 64-bit with systemd.

## Architecture

Two decoupled systemd services:

```
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│  mediamtx.service               │      │  raspizerocam.service (FastAPI) │
│                                 │      │                                 │
│  - Owns camera (rpiCamera)      │      │  - Config (JSON persist)        │
│  - Hardware H.264 encoder       │      │  - Status (CPU/RAM/WiFi)        │
│  - RTSP       :8554             │      │  - WiFi mgmt (nmcli)            │
│  - WebRTC     :8889 (HTTP)      │      │  - Web UI (/config)             │
│  - ICE UDP    :8189             │      │  - Port 8080                    │
│  - ICE TCP    :8890             │      │  - NO camera access             │
│  - HLS        :8888             │      │                                 │
│  - HTTP API   :9997             │      │                                 │
└─────────────────────────────────┘      └─────────────────────────────────┘
                ▲                                        │
                │                                        │
                └────────── restart on config change ────┘
                                (systemctl)
```

### Modules

- **app/main.py** — FastAPI app, all endpoints, lifespan (loads config, writes mediamtx.yml, restarts mediamtx, starts WiFi boot thread)
- **app/config.py** — Pydantic v2 AppConfig with Field annotations (no manual validators), JSON persistence to /opt/raspizerocam/config.json
- **app/mediamtx.py** — YAML generation from AppConfig, systemd restart helper, HTTP API client (`get_stream_state`, `get_stream_urls`), LAN IP auto-detection
- **app/status.py** — System metrics (CPU temp/usage, memory, WiFi) via /proc/* and nmcli, 3-second cache, merges in mediamtx reader count
- **app/wifi.py** — nmcli wrapper (scan, connect, AP fallback, `ensure_connected` boot sequence)
- **app/static/index.html** — Single-file config portal with WebRTC iframe preview, RTSP/WebRTC/HLS URL panel, WiFi config

### Removed (was present in Phase 1)

- `app/camera.py` — mediamtx owns the camera now
- `app/stream.py` — MJPEG generator and Pillow overlay removed
- `tests/test_stream.py` — obsolete
- CPU auto-throttle — hardware encoder doesn't stress the CPU
- Manual `_stream_clients` counter — fetched from mediamtx HTTP API instead
- `overlay` config field — live overlay feature removed

## Key Design Decisions

- **mediamtx owns the camera** — Python is never in the video hot path. This eliminated an entire class of issues from Phase 1 (software JPEG, CPU throttling, thermal crashes).
- **Clean venv, no `--system-site-packages`** — Phase 1 needed it for picamera2; Phase 2 doesn't need picamera2 at all.
- **WiFi boot in daemon thread** — FastAPI starts serving immediately so the config portal is reachable even in AP mode while trying to connect.
- **Config changes trigger mediamtx restart** — FastAPI writes new `mediamtx.yml` and calls `systemctl restart mediamtx`. ~1-2 second gap, clients reconnect automatically.
- **TCP ICE on port 8890** — default UDP 8189 and TCP 8189 are blocked on some networks (seen in our deployment LAN). Moving TCP ICE to 8890 bypasses the block. Browser mDNS ICE obfuscation (Chrome/Firefox) combined with mediamtx being a statically-linked Go binary (no mDNS resolver) means UDP WebRTC often fails; the TCP passive candidate solves it because the browser initiates the connection.
- **RTSP is the primary stream for the MyLevo use case** — WebRTC is offered but has browser compatibility gotchas. RTSP works reliably in VLC and native mobile clients.

## Known Issue: WebRTC preview may show black screen

Some browser configurations can't complete WebRTC negotiation (various combinations of mDNS obfuscation, autoplay policies, and network-specific port blocks). RTSP always works — use VLC or the native player in the MyLevo app. To try fixing WebRTC in Firefox: `about:config` → `media.peerconnection.ice.obfuscate_host_addresses` → `false`.

## Phase 2 Design Spec

See `docs/superpowers/specs/2026-04-11-phase2-design.md` for the full architecture, endpoint contracts, rationale, and migration notes from Phase 1.
