# RaspiZeroCam

Standalone MJPEG camera streaming server for Raspberry Pi Zero W.

## Features

- Low-latency MJPEG stream over HTTP (~100-200ms)
- REST API for configuration and status
- Web-based config portal with live preview
- WiFi management with AP fallback for initial setup
- Status overlay (switchable per client or globally)
- Auto-start via systemd

## Quick Start

1. Flash Raspberry Pi OS Lite (Bookworm) to SD card
2. Enable SSH and connect camera module
3. Clone and install:

```bash
git clone https://github.com/andreasschegg/RaspiZeroCam.git
cd RaspiZeroCam
./install.sh
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /stream` | MJPEG live stream (`?overlay=true` for status overlay) |
| `GET /snapshot` | Single JPEG frame |
| `GET /snapshot/info` | JPEG frame with status overlay |
| `GET /api/status` | System status (JSON) |
| `GET /api/config` | Current configuration (JSON) |
| `PUT /api/config` | Update configuration (JSON) |
| `GET /config` | Web-based config portal |

## Development

```bash
# On the Pi Zero
git pull origin main
sudo systemctl restart raspizerocam

# View logs
journalctl -u raspizerocam -f
```

## Tech Stack

Python 3.11+, FastAPI, Uvicorn, picamera2, Pillow, NetworkManager
