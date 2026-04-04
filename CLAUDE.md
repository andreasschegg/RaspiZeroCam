# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RaspiZeroCam is a standalone, headless MJPEG camera streaming server for Raspberry Pi Zero W. It provides a low-latency video stream over HTTP, a REST API, WiFi config portal, and AP fallback — all in a single FastAPI process.

**Target hardware:** Pi Zero W v1.1 (Phase 1: MJPEG), Pi Zero 2 W (Phase 2: RTSP/H.264)
**First use-case:** Rear-view camera for the MyLevo e-bike app (D:\Development\myLevo)

## Build & Test Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_config.py -v

# Run a specific test
python -m pytest tests/test_api.py::test_get_status -v

# Verify Python syntax (no hardware needed)
python -c "import ast; ast.parse(open('app/main.py').read()); print('OK')"
```

No local dev server — the app requires picamera2 hardware. Development happens on Windows, deployment via git on the Pi Zero.

## Deployment

```bash
# Deploy to Pi Zero (from Windows)
ssh <pi-zero> "cd /opt/raspizerocam && git pull && sudo systemctl restart raspizerocam"

# View logs on Pi
ssh <pi-zero> "journalctl -u raspizerocam -f"

# First-time install on Pi
ssh <pi-zero> "git clone https://github.com/andreasschegg/RaspiZeroCam.git && cd RaspiZeroCam && ./install.sh"
```

No Docker — runs directly on Raspberry Pi OS with systemd.

## Architecture

Single-process Python app: FastAPI serves both the REST API and the MJPEG stream.

```
Camera (picamera2) → FrameBuffer (thread-safe) → MJPEG Generator → StreamingResponse
                                                → Snapshot endpoint
                                                → Overlay renderer (Pillow)
```

- **app/main.py** — FastAPI app, all endpoints, lifespan (camera start/stop, WiFi boot, CPU throttle)
- **app/camera.py** — picamera2 wrapper, FrameBuffer (threading.Condition), Camera singleton. Import guarded for dev machines without picamera2.
- **app/stream.py** — MJPEG frame generator (multipart/x-mixed-replace), Pillow overlay rendering
- **app/config.py** — Pydantic AppConfig model, JSON persistence to /opt/raspizerocam/config.json
- **app/status.py** — System metrics (CPU, memory, WiFi) via /proc/* and nmcli. CPU usage uses delta-based sampling.
- **app/wifi.py** — nmcli wrapper (scan, connect, AP fallback, ensure_connected boot sequence)
- **app/static/index.html** — Single-file config portal (HTML/JS/CSS, no framework)

## Key Design Decisions

- **picamera2 import is guarded** (`HAS_PICAMERA2` flag) — app can be imported/tested on Windows
- **FrameBuffer uses threading.Condition** — wait_for_frame() blocks until a NEW frame arrives (no stale frames)
- **CPU auto-throttle** — background thread halves FPS when CPU >90%, restores when <70%
- **WiFi boot in daemon thread** — FastAPI starts serving immediately (config portal reachable in AP mode)
- **No Docker on Pi Zero** — too resource-heavy; systemd service with venv (--system-site-packages for picamera2)

## Phase 2 (planned)

RTSP/H.264 streaming via hardware encoder + mediamtx on Pi Zero 2 W. MJPEG stays as fallback. Design spec: docs/superpowers/specs/2026-04-04-raspizerocam-design.md
