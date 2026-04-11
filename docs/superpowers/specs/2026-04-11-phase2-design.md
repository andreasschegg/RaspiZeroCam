# RaspiZeroCam Phase 2 — Design Specification

**Date:** 2026-04-11
**Status:** Approved
**Project:** D:\Development\RaspiZeroCam
**Hardware:** Raspberry Pi Zero 2 W + Camera Module 3 (imx708)
**Supersedes:** Phase 2 section of `2026-04-04-raspizerocam-design.md`

## Motivation

Phase 1 delivered a working MJPEG streaming server on the Pi Zero W v1.1 with a
software JPEG encoder, topping out at 640x480 @ 7fps with ~75% CPU load. Phase 2
moves to the Pi Zero 2 W (quad-core, 512MB RAM), using the hardware H.264 encoder
via `mediamtx` to deliver 1280x720 @ 30fps at a fraction of the CPU cost, with
support for RTSP, WebRTC, and HLS out-of-the-box.

The rewrite is also a chance to strip features that were never critical (Pillow
live overlay, MJPEG fallback, auto-throttle, manual stream-client tracking) and
modernize the code (Pydantic v2 Field annotations, isolated venv, mediamtx API
for state).

## Architecture

Two separate systemd services, fully decoupled:

```
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│  mediamtx.service               │      │  raspizerocam.service           │
│                                 │      │                                 │
│  - Owns camera (rpiCamera src)  │      │  - Config (JSON persist)        │
│  - Hardware H.264 encoder       │      │  - Status (CPU/RAM/WiFi)        │
│  - RTSP       :8554             │      │  - WiFi mgmt (nmcli)            │
│  - WebRTC     :8889             │      │  - Web UI (/config)             │
│  - HLS        :8888             │      │  - Port 8080                    │
│  - HTTP API   :9997             │      │  - NO camera access             │
└─────────────────────────────────┘      └─────────────────────────────────┘
                ▲                                        │
                │                                        │
                └────────── restart on config change ────┘
                                (systemctl)
```

**Key principles:**

- **mediamtx owns the camera.** Python is not in the video hot path at all.
- **FastAPI is config + status + UI.** No frame handling, no encoding, no stream buffering.
- **Decoupled via systemd.** Config changes trigger `systemctl restart mediamtx`
  (~1-2 seconds, clients reconnect automatically).
- **Single source of truth for stream state.** Reader counts, active paths, and
  stream URLs come from the mediamtx HTTP API, not from local state.

## Stream Protocols

All three served in parallel by mediamtx from a single camera source:

| Protocol | URL                              | Use case                          |
|----------|----------------------------------|-----------------------------------|
| WebRTC   | `http://<pi>:8889/cam`           | Browser preview, lowest latency   |
| RTSP     | `rtsp://<pi>:8554/cam`           | MyLevo app, VLC, native players   |
| HLS      | `http://<pi>:8888/cam/index.m3u8`| Safari/iOS compatibility          |

**MJPEG is dropped.** It cannot coexist with mediamtx owning the camera (only
one process can hold `/dev/video0`), and WebRTC covers the browser use case with
lower latency and bandwidth.

## Camera Defaults & Ranges

| Parameter     | Default | Range            | Notes                          |
|---------------|---------|------------------|--------------------------------|
| Resolution    | 1280x720| 640x480 – 1920x1080 | Fixed list, not free-form   |
| FPS           | 30      | 15 – 60          | Hardware encoder handles 60fps |
| Bitrate       | 2000    | 500 – 5000 Kbps  | Replaces `jpeg_quality`        |
| Rotation      | 0       | 0, 180           | libcamera hflip+vflip          |

**Auto-throttle removed.** Hardware H.264 encoding doesn't stress the CPU —
sustained 30fps @ 720p costs roughly 15-25% CPU on the Pi Zero 2 W.

## Config Model

```python
class AppConfig(BaseModel):
    resolution_width: int = Field(default=1280, ge=640, le=1920)
    resolution_height: int = Field(default=720, ge=480, le=1080)
    fps: int = Field(default=30, ge=15, le=60)
    bitrate_kbps: int = Field(default=2000, ge=500, le=5000)
    rotation: Literal[0, 180] = 0
```

No more `@field_validator` methods — Pydantic v2 `Field(ge=..., le=...)` covers
all range checks declaratively. The `overlay` field is gone.

## HTTP Endpoints (FastAPI)

### Config & Status

| Endpoint        | Method | Description                                        |
|-----------------|--------|----------------------------------------------------|
| `/api/config`   | GET    | Current `AppConfig` as JSON                        |
| `/api/config`   | PUT    | Update config → save → regenerate mediamtx.yml → restart |
| `/api/status`   | GET    | CPU temp, CPU usage, RAM, WiFi, uptime, mediamtx state |
| `/api/streams`  | GET    | `{ webrtc, rtsp, hls, snapshot }` URLs             |

### Snapshot

| Endpoint        | Method | Description                                        |
|-----------------|--------|----------------------------------------------------|
| `/snapshot`     | GET    | Proxy to mediamtx HTTP snapshot API                |

### WiFi Management (unchanged from Phase 1)

| Endpoint                | Method | Description                    |
|-------------------------|--------|--------------------------------|
| `/config/wifi/scan`     | POST   | `[{ ssid, signal, encrypted }]` |
| `/config/wifi`          | POST   | `{ ssid, password }` → connect  |
| `/config/wifi/saved`    | GET    | List of saved connections      |
| `/config/wifi/{name}`   | DELETE | Remove saved connection        |

### Config Portal

| Endpoint        | Method | Description                                        |
|-----------------|--------|----------------------------------------------------|
| `/config`       | GET    | Serves `app/static/index.html`                     |
| `/static/*`     | GET    | Static assets (JS, CSS if any)                     |

### Removed from Phase 1

- `/stream` (MJPEG multipart) — replaced by mediamtx WebRTC/RTSP
- `/snapshot/info` (Pillow overlay on JPEG) — overlay feature dropped
- All `?overlay=true` query parameter logic

## Status Response

```python
class StatusResponse(BaseModel):
    cpu_temperature: float         # °C
    cpu_usage: float               # %
    memory: MemoryInfo
    wifi: WifiInfo
    uptime_seconds: int
    camera_running: bool           # from mediamtx API
    stream_readers: int            # from mediamtx API
```

`camera_running` and `stream_readers` are fetched from mediamtx's
`/v3/paths/get/cam` endpoint. No local state tracking in FastAPI.

**Status cache** reduced from 10s to 3s. `nmcli` is fast enough on the Pi Zero
2 W that the longer cache is no longer necessary, and 3s gives a more live feel
in the UI without flooding nmcli with calls.

## Project Structure

```
raspizerocam/
├── app/
│   ├── main.py              # FastAPI app, endpoints, lifespan
│   ├── config.py            # AppConfig (Pydantic v2), load/save
│   ├── status.py            # CPU/RAM/WiFi, status cache (3s TTL)
│   ├── wifi.py              # nmcli wrapper (unchanged)
│   ├── mediamtx.py          # NEW: YAML generation + API client
│   └── static/
│       └── index.html       # Config portal (WebRTC player embedded)
├── deploy/
│   ├── raspizerocam.service # systemd unit for FastAPI
│   ├── mediamtx.service     # NEW: systemd unit for mediamtx
│   └── mediamtx.yml.template # Base mediamtx config
├── install.sh               # Installs mediamtx binary + both services
├── requirements.txt         # fastapi, uvicorn, pydantic, pytest, httpx
└── tests/                   # Updated for Phase 2 endpoints
```

**Removed files:**
- `app/camera.py` — camera ownership moved to mediamtx
- `app/stream.py` — MJPEG generator + Pillow overlay gone
- `raspizerocam.service` (root) → moved to `deploy/`

**Removed dependencies:**
- `pillow` — overlay feature dropped
- `python3-picamera2` system package — mediamtx handles camera directly
- `--system-site-packages` flag on venv — sauber isolated venv

## mediamtx Configuration

mediamtx is configured via `/opt/raspizerocam/mediamtx.yml`, generated from
`AppConfig` by `app/mediamtx.py`:

```yaml
# Generated from AppConfig — do not edit manually
logLevel: info

api: yes
apiAddress: :9997

rtspAddress: :8554
webrtcAddress: :8889
hlsAddress: :8888

paths:
  cam:
    source: rpiCamera
    rpiCameraWidth: 1280
    rpiCameraHeight: 720
    rpiCameraFPS: 30
    rpiCameraBitrate: 2000000
    rpiCameraHFlip: false
    rpiCameraVFlip: false
    rpiCameraCodec: h264
```

On `PUT /api/config`:
1. Validate new config via Pydantic
2. Save `config.json`
3. Regenerate `mediamtx.yml` from new config
4. `systemctl restart mediamtx` via subprocess
5. Return the new config

## Web UI Changes

`app/static/index.html` is updated:

- **Live preview** — replaces `<img src="/stream">` with a `<video>` element
  driven by mediamtx's reference WebRTC player (~200 lines of inline vanilla JS,
  no framework, matches the "no build pipeline" philosophy).
- **Resolution dropdown** — 640x480 / 1280x720 / 1920x1080.
- **FPS slider** — 15-60.
- **Bitrate slider** — 500-5000 Kbps (replaces jpeg_quality slider).
- **Rotation toggle** — 0° / 180° (unchanged).
- **Stream URLs panel** — displays the RTSP/WebRTC/HLS URLs so you can copy
  them for VLC, the MyLevo app, etc.
- **Removed:** Overlay toggle, "throttled" indicator.

## Startup Sequence

FastAPI lifespan:

1. Load `config.json` (or defaults)
2. Start WiFi boot thread (daemon) — tries saved networks, falls back to AP
3. Write `mediamtx.yml` from current config
4. `systemctl start mediamtx` (idempotent — service may already be running)
5. Serve HTTP

Note: `cpu_throttle_monitor` daemon thread is gone. There's nothing to throttle
when the hardware encoder handles the stream.

## Deployment

### install.sh

```bash
#!/bin/bash
set -e

# 1. System packages (no picamera2 needed anymore)
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip network-manager

# 2. mediamtx binary (arm64)
MEDIAMTX_VERSION="1.9.0"
wget "https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_linux_arm64.tar.gz"
tar -xzf mediamtx_v${MEDIAMTX_VERSION}_linux_arm64.tar.gz
sudo mv mediamtx /usr/local/bin/
rm mediamtx_v${MEDIAMTX_VERSION}_linux_arm64.tar.gz

# 3. Project location
sudo mkdir -p /opt/raspizerocam
sudo cp -r app /opt/raspizerocam/
sudo cp requirements.txt /opt/raspizerocam/

# 4. venv (NO --system-site-packages — clean isolation)
sudo python3 -m venv /opt/raspizerocam/venv
sudo /opt/raspizerocam/venv/bin/pip install -r /opt/raspizerocam/requirements.txt

# 5. systemd services
sudo cp deploy/raspizerocam.service /etc/systemd/system/
sudo cp deploy/mediamtx.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable raspizerocam mediamtx
sudo systemctl start mediamtx raspizerocam
```

### systemd units

**`deploy/mediamtx.service`:**
```ini
[Unit]
Description=mediamtx streaming server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mediamtx /opt/raspizerocam/mediamtx.yml
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

**`deploy/raspizerocam.service`** — mostly unchanged from Phase 1, but
`WorkingDirectory=/opt/raspizerocam` and the venv path stay the same.

## Testing

- `tests/test_config.py` — Pydantic v2 validation, load/save roundtrip
- `tests/test_mediamtx.py` — YAML generation from AppConfig, restart trigger (mocked)
- `tests/test_api.py` — FastAPI TestClient for config/status/streams endpoints
- `tests/test_wifi.py` — nmcli mock tests (unchanged from Phase 1)

No live-hardware tests in CI — those remain manual on the Pi.

## Non-Goals for Phase 2

- **No recording / DVR** — mediamtx supports it, but out of scope.
- **No authentication** — private network use only, unchanged.
- **No motion detection**
- **No metrics/Prometheus export**
- **No MJPEG fallback**

## Open Migration Steps (from Phase 1 codebase)

1. Delete `app/camera.py`, `app/stream.py`, `raspizerocam.service` (root).
2. Rewrite `app/config.py` with new fields + Field annotations.
3. Rewrite `app/main.py`: remove camera lifecycle, MJPEG endpoints, throttle
   monitor, stream client counter. Add mediamtx restart trigger and new
   `/api/streams` endpoint.
4. Write `app/mediamtx.py`: YAML generation, HTTP API client for status/readers.
5. Update `app/status.py`: remove cpu_throttle priming, reduce cache to 3s,
   merge in mediamtx reader count.
6. Update `app/static/index.html`: new controls, WebRTC player, stream URL
   panel.
7. Write `deploy/mediamtx.service` and `deploy/mediamtx.yml.template`.
8. Move `raspizerocam.service` to `deploy/`.
9. Rewrite `install.sh`.
10. Update tests.
11. Deploy to `raspizerocam` (192.168.33.55), verify all three stream
    protocols work end-to-end.
