# RaspiZeroCam — Design Specification

**Date:** 2026-04-04
**Status:** Approved
**Project:** D:\Development\RaspiZeroCam

## Overview

RaspiZeroCam is a standalone, headless camera streaming module running on a Raspberry Pi Zero. It provides a low-latency video stream over HTTP and a REST API for configuration and status monitoring. The module connects to existing WiFi networks (e.g., phone hotspot or home WiFi) and is accessible from any client — browser, mobile app, or media player.

**First use-case:** Rear-view camera for the MyLevo e-bike app, replacing the GoPro Hero 12 with a cheaper, dedicated hardware solution. The MyLevo integration will happen as a separate project step; this spec covers the standalone module only.

## Phased Approach

### Phase 1 — MJPEG on Pi Zero W v1.1

- Existing hardware: Raspberry Pi Zero W v1.1 (single-core 1GHz, 512MB RAM, 802.11n)
- MJPEG stream over HTTP (multipart/x-mixed-replace)
- Target: 640x480 @ 15fps, JPEG quality 70%
- Latency: ~100-200ms

### Phase 2 — RTSP/H.264 on Pi Zero 2 W

- New hardware: Raspberry Pi Zero 2 W (quad-core 1GHz, 512MB RAM, 802.11n)
- Additional RTSP/H.264 stream via hardware encoder + mediamtx
- Endpoint: `rtsp://<ip>:8554/cam`
- MJPEG endpoint remains available in parallel
- Configurable which stream mode is active

Both phases will be deployed and tested live for comparison.

## Architecture

```
┌─────────────────────────────────────┐
│         RaspiZeroCam (Pi Zero)      │
│                                     │
│  ┌───────────┐    ┌──────────────┐  │
│  │ libcamera │───▶│ Stream Engine│  │
│  │ (camera)  │    │ MJPEG/RTSP   │  │
│  └───────────┘    └──────┬───────┘  │
│                          │          │
│  ┌───────────┐    ┌──────▼───────┐  │
│  │ Config    │───▶│  Web Server  │  │
│  │ Portal    │    │  (FastAPI)   │  │
│  └───────────┘    └──────┬───────┘  │
│                          │          │
│  ┌───────────┐    ┌──────▼───────┐  │
│  │ WiFi Mgr  │    │  REST API    │  │
│  │ (nmcli)   │    │  /stream     │  │
│  └───────────┘    │  /api/status │  │
│                   │  /api/config │  │
│                   │  /config (UI)│  │
│                   └──────────────┘  │
└─────────────────────────────────────┘
        ▲ WiFi (STA mode)
        │
   Pixel Hotspot / Home WiFi
        │
        ▼
┌──────────────┐   ┌──────────────┐
│  MyLevo App  │   │   Browser    │
│  (later)     │   │  (immediate) │
└──────────────┘   └──────────────┘
```

**Core principles:**
- **Single process** — FastAPI server with integrated camera access, no separate streaming daemon
- **Headless** — No monitor, no desktop. API + stream only
- **AP fallback** — If no known WiFi is found, the Pi opens a temporary AP with a config portal
- **No Docker** — Too resource-heavy for Pi Zero W. Runs directly on the OS with systemd

## HTTP Endpoints & API

### Stream Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream` | GET | MJPEG stream (multipart/x-mixed-replace). Supports `?overlay=true` query parameter for per-client status overlay |
| `/snapshot` | GET | Single JPEG frame (current camera image) |
| `/snapshot/info` | GET | JPEG frame with semi-transparent text overlay showing current config and network info |

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | JSON: camera status, resolution, FPS, uptime, WiFi signal, CPU temp, active clients |
| `/api/config` | GET | JSON: current configuration |
| `/api/config` | PUT | JSON: update configuration at runtime (resolution, FPS, quality, rotation, overlay) |

### Config Portal

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/config` | GET | Web-UI (single-page HTML/JS) |
| `/config/wifi` | POST | Save WiFi credentials and connect |
| `/config/wifi/scan` | POST | Scan and list available WiFi networks |

### Overlay Content

The status overlay (on `/snapshot/info` and `/stream?overlay=true`) renders the following as semi-transparent text on the camera image via Pillow:

- Resolution, FPS, JPEG quality
- WiFi SSID, signal strength (dBm)
- IP address, hostname
- Uptime, CPU temperature
- Stream mode (MJPEG / RTSP in Phase 2)
- Timestamp

The overlay can be activated:
- **Per client:** `GET /stream?overlay=true` — only that client sees the overlay
- **Globally:** `PUT /api/config { "overlay": true }` — all clients see the overlay

## WiFi Management & AP Fallback

### Boot Sequence

```
Pi Zero boots
    │
    ▼
Known WiFi found?
    ├─ YES → Connect → Start stream → ready
    │
    └─ NO → Start AP fallback
                │
                ▼
         AP: "RaspiZeroCam-XXXX" (open network, last 4 of MAC)
         IP: 192.168.4.1
         Config portal at http://192.168.4.1/config
                │
                ▼
         User connects with phone/laptop
         → WiFi scan → Enter credentials → Save
                │
                ▼
         Shut down AP → Connect to chosen network → Start stream
```

### Details

- **NetworkManager (nmcli)** for WiFi management — standard on Raspberry Pi OS Bookworm, more robust than wpa_supplicant
- **Multiple WiFi networks storable** — e.g., Pixel hotspot + home WiFi. NetworkManager automatically selects the strongest available
- **AP name** includes last 4 characters of MAC address (e.g., "RaspiZeroCam-A3F2") — distinguishes multiple modules
- **No password on AP** — temporary for config only, not a security risk
- **Timeout** — If no credentials entered after 5 minutes in AP mode, retry scanning for known networks. Endless loop until a network is found.
- **Status LED** (if GPIO available): slow blink = searching WiFi, fast blink = AP mode, solid = connected and streaming

## Camera & Stream Engine

### Phase 1 — MJPEG

- **Camera access** via `picamera2` (Python library, official libcamera wrapper)
- **Target parameters:** 640x480 @ 15fps, JPEG quality 70%
- **Architecture:** picamera2 delivers JPEG frames → FastAPI endpoint iterates over frames as `multipart/x-mixed-replace` response
- **Single-producer, multi-consumer:** One thread captures frames into a ring buffer, multiple clients read from it. Camera is accessed only once.
- **Overlay rendering:** When enabled, Pillow renders a text overlay onto the frame before delivery. Decidable per client (query param) or globally (config).
- **Auto-throttle:** If CPU is sustained >90%, FPS is automatically reduced to keep the stream stable. Reported in `/api/status`.

### Phase 2 — RTSP/H.264 (Pi Zero 2 W)

- `libcamera-vid` with hardware H.264 encoder (Pi GPU) → pipe to `mediamtx` RTSP server
- Endpoint: `rtsp://<ip>:8554/cam`
- MJPEG endpoint remains available in parallel
- Configurable which stream mode is active via `/api/config`

### Configurable Parameters (runtime, no restart required)

| Parameter | Default | Range |
|-----------|---------|-------|
| resolution | 640x480 | 320x240 – 1280x720 |
| fps | 15 | 5 – 30 |
| jpeg_quality | 70 | 30 – 95 |
| rotation | 0 | 0, 180 |
| overlay | false | true / false |

## Config Portal (Web-UI)

Single-page HTML/JS application served directly by FastAPI. No frontend framework — plain HTML + vanilla JS + minimal CSS. Everything in a single `index.html` with inline JS/CSS — no build pipeline, no dependencies.

### Sections

1. **WiFi Configuration**
   - Scan available networks and display as list (signal strength, encrypted yes/no)
   - Enter SSID + password or select from list
   - Show / delete saved networks
   - Live connection status display

2. **Camera Settings**
   - Resolution, FPS, JPEG quality via slider/dropdown
   - Rotation (0° / 180°) toggle
   - Overlay on/off
   - Live preview of stream embedded via `<img src="/stream">`

3. **Status Page**
   - CPU temperature, CPU load, RAM usage
   - WiFi signal, IP address, uptime
   - Active stream clients (count)
   - Hostname, software version

**Design principle:** Functional, no styling effort. Mobile-first (mostly accessed from phone), responsive via simple CSS Grid.

## Project Structure

```
raspizerocam/
├── app/
│   ├── main.py              # FastAPI app, endpoints, startup
│   ├── camera.py            # Camera access, frame buffer, picamera2
│   ├── stream.py            # MJPEG stream generator, overlay logic
│   ├── config.py            # Configuration management (JSON file)
│   ├── wifi.py              # WiFi scan, connect, AP fallback (nmcli)
│   ├── status.py            # System status (CPU, temp, RAM, WiFi)
│   └── static/
│       └── index.html       # Config portal (single-file web-UI)
├── config.json              # Persistent configuration
├── install.sh               # Setup script: dependencies, systemd service
├── raspizerocam.service     # systemd unit file (autostart)
├── requirements.txt         # Python dependencies
└── README.md
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ (pre-installed on Raspberry Pi OS Bookworm) |
| Web Server | FastAPI + Uvicorn |
| Camera | picamera2 (official libcamera wrapper) |
| Overlay | Pillow (PIL) |
| WiFi Management | NetworkManager / nmcli (via subprocess) |
| RTSP (Phase 2) | mediamtx + libcamera-vid |
| Process Manager | systemd |
| OS | Raspberry Pi OS Lite (Bookworm) |

## Deployment

- **No Docker** — too resource-heavy for Pi Zero W. Runs directly on the OS.
- **systemd service** — Autostart at boot, automatic restart on crash
- **Config persistence** — `config.json` in project directory, survives restarts
- **Installation:** Git clone or SCP to `/opt/raspizerocam/`, run `install.sh`
- **Updates:** `git pull && sudo systemctl restart raspizerocam`

### Development Workflow

1. Write code on Windows PC
2. Push to GitHub via git
3. SSH to Pi Zero: `git pull && sudo systemctl restart raspizerocam`

## Explicit Non-Goals (Phase 1)

- No recording / dashcam functionality
- No motion detection
- No BLE communication
- No MyLevo app integration (separate project step)
- No authentication (private network only)
- No power supply solution (software first)

## Future Integration: MyLevo App

When integrating into MyLevo, the plan is to build an abstract camera interface that supports multiple backends (GoPro, RaspiZeroCam, potentially others). The biker can then choose their preferred rear-view camera source in settings. This will be designed and implemented as a separate project.
