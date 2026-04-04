# RaspiZeroCam Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone MJPEG streaming server on a Raspberry Pi Zero W that provides a live camera feed, REST API, WiFi config portal, and AP fallback — all in a single FastAPI process.

**Architecture:** Single-process Python app using FastAPI + Uvicorn. picamera2 captures JPEG frames into a thread-safe ring buffer. Multiple HTTP clients consume frames via MJPEG streaming response. NetworkManager (nmcli) handles WiFi with AP fallback for initial config.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, picamera2, Pillow, nmcli (subprocess)

---

## File Structure

```
raspizerocam/
├── app/
│   ├── main.py              # FastAPI app, lifespan, route mounting
│   ├── camera.py            # picamera2 wrapper, frame buffer, capture thread
│   ├── stream.py            # MJPEG generator, overlay rendering
│   ├── config.py            # Config model (Pydantic), JSON persistence
│   ├── wifi.py              # nmcli wrapper: scan, connect, AP fallback
│   ├── status.py            # System metrics: CPU, temp, RAM, WiFi signal
│   └── static/
│       └── index.html       # Config portal (single-file web-UI)
├── tests/
│   ├── test_config.py       # Config load/save/validate tests
│   ├── test_stream.py       # MJPEG boundary format, overlay toggle tests
│   ├── test_status.py       # Status parsing tests
│   ├── test_wifi.py         # nmcli command builder tests
│   └── test_api.py          # FastAPI endpoint integration tests
├── config.json              # Persistent configuration (created at first run)
├── install.sh               # Setup script: venv, deps, systemd service
├── raspizerocam.service     # systemd unit file
├── requirements.txt         # Python dependencies
└── README.md
```

---

## Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize git repo and create requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
picamera2==0.3.22
pillow==10.4.0
pydantic==2.9.0
pytest==8.3.0
httpx==0.27.0
```

- [ ] **Step 2: Create empty package init files**

Create `app/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt app/__init__.py tests/__init__.py
git commit -m "feat: project scaffolding with dependencies"
```

---

## Task 2: Configuration Management

**Files:**
- Create: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import json
import os
import pytest
from app.config import AppConfig, load_config, save_config

DEFAULT_CONFIG_PATH = "test_config.json"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DEFAULT_CONFIG_PATH):
        os.remove(DEFAULT_CONFIG_PATH)


def test_default_config_values():
    config = AppConfig()
    assert config.resolution_width == 640
    assert config.resolution_height == 480
    assert config.fps == 15
    assert config.jpeg_quality == 70
    assert config.rotation == 0
    assert config.overlay is False


def test_save_and_load_config():
    config = AppConfig(fps=10, jpeg_quality=50)
    save_config(config, DEFAULT_CONFIG_PATH)
    loaded = load_config(DEFAULT_CONFIG_PATH)
    assert loaded.fps == 10
    assert loaded.jpeg_quality == 50


def test_load_missing_file_returns_defaults():
    loaded = load_config("nonexistent.json")
    assert loaded.resolution_width == 640
    assert loaded.fps == 15


def test_partial_update():
    config = AppConfig()
    updated = config.model_copy(update={"fps": 25, "overlay": True})
    assert updated.fps == 25
    assert updated.overlay is True
    assert updated.resolution_width == 640


def test_validation_rejects_invalid_fps():
    with pytest.raises(ValueError):
        AppConfig(fps=0)


def test_validation_rejects_invalid_quality():
    with pytest.raises(ValueError):
        AppConfig(jpeg_quality=100)


def test_validation_rejects_invalid_rotation():
    with pytest.raises(ValueError):
        AppConfig(rotation=90)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Write the implementation**

```python
# app/config.py
import json
import os
from pydantic import BaseModel, field_validator


class AppConfig(BaseModel):
    resolution_width: int = 640
    resolution_height: int = 480
    fps: int = 15
    jpeg_quality: int = 70
    rotation: int = 0
    overlay: bool = False

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, v: int) -> int:
        if not 5 <= v <= 30:
            raise ValueError(f"fps must be between 5 and 30, got {v}")
        return v

    @field_validator("jpeg_quality")
    @classmethod
    def validate_jpeg_quality(cls, v: int) -> int:
        if not 30 <= v <= 95:
            raise ValueError(f"jpeg_quality must be between 30 and 95, got {v}")
        return v

    @field_validator("rotation")
    @classmethod
    def validate_rotation(cls, v: int) -> int:
        if v not in (0, 180):
            raise ValueError(f"rotation must be 0 or 180, got {v}")
        return v

    @field_validator("resolution_width")
    @classmethod
    def validate_width(cls, v: int) -> int:
        if not 320 <= v <= 1280:
            raise ValueError(f"resolution_width must be between 320 and 1280, got {v}")
        return v

    @field_validator("resolution_height")
    @classmethod
    def validate_height(cls, v: int) -> int:
        if not 240 <= v <= 720:
            raise ValueError(f"resolution_height must be between 240 and 720, got {v}")
        return v


CONFIG_PATH = "/opt/raspizerocam/config.json"


def load_config(path: str = CONFIG_PATH) -> AppConfig:
    if not os.path.exists(path):
        return AppConfig()
    with open(path, "r") as f:
        data = json.load(f)
    return AppConfig(**data)


def save_config(config: AppConfig, path: str = CONFIG_PATH) -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: configuration management with Pydantic validation and JSON persistence"
```

---

## Task 3: System Status Module

**Files:**
- Create: `app/status.py`
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_status.py
from unittest.mock import patch, mock_open
from app.status import get_cpu_temperature, get_cpu_usage, get_memory_usage, get_wifi_info, get_system_status


def test_parse_cpu_temperature():
    with patch("builtins.open", mock_open(read_data="54321")):
        temp = get_cpu_temperature()
    assert temp == 54.3


def test_cpu_temperature_file_missing():
    with patch("builtins.open", side_effect=FileNotFoundError):
        temp = get_cpu_temperature()
    assert temp == 0.0


def test_parse_cpu_usage():
    stat_lines = "cpu  1000 200 300 5000 100 0 50 0 0 0\n"
    with patch("builtins.open", mock_open(read_data=stat_lines)):
        usage = get_cpu_usage()
    assert isinstance(usage, float)
    assert 0.0 <= usage <= 100.0


def test_parse_memory_usage():
    meminfo = "MemTotal:      512000 kB\nMemAvailable:  256000 kB\n"
    with patch("builtins.open", mock_open(read_data=meminfo)):
        mem = get_memory_usage()
    assert mem["total_mb"] == 500.0
    assert mem["available_mb"] == 250.0
    assert mem["usage_percent"] == 50.0


def test_wifi_info_connected():
    nmcli_output = "MyNetwork:72:192.168.4.100"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = nmcli_output
        mock_run.return_value.returncode = 0
        info = get_wifi_info()
    assert info["ssid"] == "MyNetwork"
    assert info["signal_dbm"] == "72"
    assert info["ip_address"] == "192.168.4.100"


def test_wifi_info_disconnected():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        info = get_wifi_info()
    assert info["ssid"] == ""
    assert info["ip_address"] == ""


def test_system_status_returns_all_fields():
    with patch("app.status.get_cpu_temperature", return_value=45.0), \
         patch("app.status.get_cpu_usage", return_value=23.5), \
         patch("app.status.get_memory_usage", return_value={"total_mb": 500.0, "available_mb": 300.0, "usage_percent": 40.0}), \
         patch("app.status.get_wifi_info", return_value={"ssid": "Test", "signal_dbm": "65", "ip_address": "10.0.0.1"}), \
         patch("app.status.get_uptime_seconds", return_value=3600):
        status = get_system_status()
    assert status["cpu_temperature"] == 45.0
    assert status["cpu_usage"] == 23.5
    assert status["memory"]["total_mb"] == 500.0
    assert status["wifi"]["ssid"] == "Test"
    assert status["uptime_seconds"] == 3600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.status'`

- [ ] **Step 3: Write the implementation**

```python
# app/status.py
import subprocess
import time

_boot_time = time.time()


def get_cpu_temperature() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (FileNotFoundError, ValueError):
        return 0.0


def get_cpu_usage() -> float:
    with open("/proc/stat", "r") as f:
        parts = f.readline().split()
    idle = int(parts[4])
    total = sum(int(p) for p in parts[1:])
    if total == 0:
        return 0.0
    return round((1 - idle / total) * 100, 1)


def get_memory_usage() -> dict:
    mem = {}
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                mem["total_mb"] = round(int(line.split()[1]) / 1024, 1)
            elif line.startswith("MemAvailable:"):
                mem["available_mb"] = round(int(line.split()[1]) / 1024, 1)
    mem["usage_percent"] = round((1 - mem["available_mb"] / mem["total_mb"]) * 100, 1)
    return mem


def get_wifi_info() -> dict:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,IP4.ADDRESS", "device", "wifi"],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            return {
                "ssid": parts[0],
                "signal_dbm": parts[1],
                "ip_address": parts[2],
            }
    return {"ssid": "", "signal_dbm": "", "ip_address": ""}


def get_uptime_seconds() -> int:
    return int(time.time() - _boot_time)


def get_system_status() -> dict:
    return {
        "cpu_temperature": get_cpu_temperature(),
        "cpu_usage": get_cpu_usage(),
        "memory": get_memory_usage(),
        "wifi": get_wifi_info(),
        "uptime_seconds": get_uptime_seconds(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/status.py tests/test_status.py
git commit -m "feat: system status module for CPU, memory, WiFi metrics"
```

---

## Task 4: WiFi Management & AP Fallback

**Files:**
- Create: `app/wifi.py`
- Test: `tests/test_wifi.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wifi.py
from unittest.mock import patch, MagicMock
from app.wifi import scan_networks, connect_to_network, get_saved_networks, delete_network, WifiNetwork, start_ap, stop_ap, get_mac_suffix


def test_parse_scan_results():
    nmcli_output = (
        "MyNetwork:80:WPA2\n"
        "OpenNet:45:\n"
        "StrongNet:92:WPA2\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = nmcli_output
        mock_run.return_value.returncode = 0
        networks = scan_networks()
    assert len(networks) == 3
    assert networks[0].ssid == "MyNetwork"
    assert networks[0].signal == 80
    assert networks[0].encrypted is True
    assert networks[1].ssid == "OpenNet"
    assert networks[1].encrypted is False


def test_connect_to_network_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        result = connect_to_network("TestSSID", "password123")
    assert result is True
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "TestSSID" in cmd
    assert "password123" in cmd


def test_connect_to_network_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error"
        result = connect_to_network("BadSSID", "wrong")
    assert result is False


def test_get_saved_networks():
    nmcli_output = "Home-WiFi:802-11-wireless\nPixel-Hotspot:802-11-wireless\nEthernet:802-3-ethernet\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = nmcli_output
        mock_run.return_value.returncode = 0
        saved = get_saved_networks()
    assert saved == ["Home-WiFi", "Pixel-Hotspot"]


def test_delete_network():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = delete_network("OldNetwork")
    assert result is True
    cmd = mock_run.call_args[0][0]
    assert "delete" in cmd
    assert "OldNetwork" in cmd


def test_get_mac_suffix():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "AA:BB:CC:DD:EE:FF\n"
        mock_run.return_value.returncode = 0
        suffix = get_mac_suffix()
    assert suffix == "EEFF"


def test_start_ap_uses_mac_suffix():
    with patch("app.wifi.get_mac_suffix", return_value="A3F2"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        start_ap()
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "RaspiZeroCam-A3F2" in cmd_str
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wifi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.wifi'`

- [ ] **Step 3: Write the implementation**

```python
# app/wifi.py
import subprocess
from dataclasses import dataclass


@dataclass
class WifiNetwork:
    ssid: str
    signal: int
    encrypted: bool


def scan_networks() -> list[WifiNetwork]:
    subprocess.run(["nmcli", "device", "wifi", "rescan"], capture_output=True)
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
        capture_output=True, text=True
    )
    networks = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            networks.append(WifiNetwork(
                ssid=parts[0],
                signal=int(parts[1]) if parts[1] else 0,
                encrypted=bool(parts[2].strip()),
            ))
    return networks


def connect_to_network(ssid: str, password: str) -> bool:
    result = subprocess.run(
        ["nmcli", "device", "wifi", "connect", ssid, "password", password],
        capture_output=True, text=True
    )
    return result.returncode == 0


def get_saved_networks() -> list[str]:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        capture_output=True, text=True
    )
    networks = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            networks.append(parts[0])
    return networks


def delete_network(name: str) -> bool:
    result = subprocess.run(
        ["nmcli", "connection", "delete", name],
        capture_output=True, text=True
    )
    return result.returncode == 0


def get_mac_suffix() -> str:
    result = subprocess.run(
        ["cat", "/sys/class/net/wlan0/address"],
        capture_output=True, text=True
    )
    mac = result.stdout.strip().upper()
    return mac.replace(":", "")[-4:]


def start_ap() -> None:
    suffix = get_mac_suffix()
    ssid = f"RaspiZeroCam-{suffix}"
    subprocess.run([
        "nmcli", "device", "wifi", "hotspot",
        "ifname", "wlan0",
        "ssid", ssid,
        "band", "bg",
        "channel", "6",
    ], capture_output=True, text=True)


def stop_ap() -> None:
    subprocess.run(
        ["nmcli", "connection", "down", "Hotspot"],
        capture_output=True, text=True
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wifi.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/wifi.py tests/test_wifi.py
git commit -m "feat: WiFi management with scan, connect, AP fallback via nmcli"
```

---

## Task 5: Camera Module & Frame Buffer

**Files:**
- Create: `app/camera.py`

Note: picamera2 requires actual camera hardware, so this module cannot be unit-tested on the dev machine. It will be tested manually on the Pi Zero after deployment. The stream module (Task 6) will be testable with mock frames.

- [ ] **Step 1: Write the camera module**

```python
# app/camera.py
import threading
import time
import logging

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput
    HAS_PICAMERA2 = True
except ImportError:
    HAS_PICAMERA2 = False


class FrameBuffer:
    def __init__(self):
        self._frame: bytes | None = None
        self._condition = threading.Condition()

    def update(self, frame: bytes) -> None:
        with self._condition:
            self._frame = frame
            self._condition.notify_all()

    def wait_for_frame(self, timeout: float = 2.0) -> bytes | None:
        with self._condition:
            if self._frame is None:
                self._condition.wait(timeout=timeout)
            return self._frame


class _StreamOutput:
    """Custom output that picamera2's MJPEGEncoder writes JPEG frames to."""

    def __init__(self, buffer: FrameBuffer):
        self._buffer = buffer

    def write(self, data: bytes) -> None:
        self._buffer.update(data)

    def flush(self) -> None:
        pass


class Camera:
    def __init__(self):
        self._picam2: Picamera2 | None = None
        self._buffer = FrameBuffer()
        self._running = False

    @property
    def buffer(self) -> FrameBuffer:
        return self._buffer

    def start(self, width: int = 640, height: int = 480, fps: int = 15) -> None:
        if not HAS_PICAMERA2:
            logger.warning("picamera2 not available — camera disabled")
            return

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self._picam2.configure(config)
        self._picam2.set_controls({"FrameRate": float(fps)})

        encoder = MJPEGEncoder()
        output = FileOutput(_StreamOutput(self._buffer))
        self._picam2.start_recording(encoder, output)
        self._running = True
        logger.info(f"Camera started: {width}x{height} @ {fps}fps")

    def stop(self) -> None:
        if self._picam2 and self._running:
            self._picam2.stop_recording()
            self._picam2.close()
            self._running = False
            logger.info("Camera stopped")

    def restart(self, width: int, height: int, fps: int) -> None:
        self.stop()
        time.sleep(0.5)
        self.start(width, height, fps)

    @property
    def is_running(self) -> bool:
        return self._running


# Singleton instance
camera = Camera()
```

- [ ] **Step 2: Verify syntax is valid**

Run: `python -c "import ast; ast.parse(open('app/camera.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/camera.py
git commit -m "feat: camera module with picamera2 wrapper and thread-safe frame buffer"
```

---

## Task 6: MJPEG Stream Generator & Overlay

**Files:**
- Create: `app/stream.py`
- Test: `tests/test_stream.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stream.py
import pytest
from unittest.mock import MagicMock, patch
from app.stream import generate_mjpeg_frames, render_overlay
from app.camera import FrameBuffer


def _make_fake_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0fake_jpeg_data\xff\xd9"


def test_mjpeg_frame_format():
    buffer = FrameBuffer()
    buffer.update(_make_fake_jpeg())

    frames = generate_mjpeg_frames(buffer, overlay=False)
    chunk = next(frames)
    assert b"--frame\r\n" in chunk
    assert b"Content-Type: image/jpeg\r\n" in chunk
    assert b"\xff\xd8" in chunk


def test_mjpeg_returns_none_on_timeout():
    buffer = FrameBuffer()
    frames = generate_mjpeg_frames(buffer, overlay=False, timeout=0.1)
    chunk = next(frames)
    assert chunk == b""


def test_overlay_renders_text_on_image():
    fake_jpeg = _make_fake_jpeg()
    status = {
        "cpu_temperature": 45.0,
        "wifi": {"ssid": "TestNet", "signal_dbm": "72", "ip_address": "10.0.0.1"},
        "uptime_seconds": 120,
    }
    config = {"resolution_width": 640, "resolution_height": 480, "fps": 15, "jpeg_quality": 70}

    with patch("app.stream.Image") as mock_image_mod:
        mock_img = MagicMock()
        mock_image_mod.open.return_value = mock_img
        mock_img.size = (640, 480)

        mock_draw_cls = MagicMock()
        with patch("app.stream.ImageDraw") as mock_draw_mod:
            mock_draw_mod.Draw.return_value = mock_draw_cls

            with patch("app.stream.BytesIO") as mock_bytes:
                mock_bytes.return_value.getvalue.return_value = b"jpeg_with_overlay"
                result = render_overlay(fake_jpeg, status, config)

    assert result == b"jpeg_with_overlay"
    mock_draw_cls.text.assert_called()


def test_generate_frames_with_overlay():
    buffer = FrameBuffer()
    buffer.update(_make_fake_jpeg())

    with patch("app.stream.render_overlay", return_value=b"overlaid_jpeg") as mock_overlay, \
         patch("app.stream.get_system_status", return_value={}):
        frames = generate_mjpeg_frames(buffer, overlay=True)
        chunk = next(frames)
    assert b"overlaid_jpeg" in chunk
    mock_overlay.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stream.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.stream'`

- [ ] **Step 3: Write the implementation**

```python
# app/stream.py
import time
from io import BytesIO
from typing import Generator
from PIL import Image, ImageDraw, ImageFont

from app.camera import FrameBuffer
from app.status import get_system_status


def render_overlay(jpeg_bytes: bytes, status: dict, config: dict) -> bytes:
    img = Image.open(BytesIO(jpeg_bytes))
    draw = ImageDraw.Draw(img, "RGBA")

    lines = [
        f"{config.get('resolution_width', '?')}x{config.get('resolution_height', '?')} @ {config.get('fps', '?')}fps  Q:{config.get('jpeg_quality', '?')}",
        f"WiFi: {status.get('wifi', {}).get('ssid', 'N/A')}  Signal: {status.get('wifi', {}).get('signal_dbm', '?')} dBm",
        f"IP: {status.get('wifi', {}).get('ip_address', 'N/A')}",
        f"CPU: {status.get('cpu_temperature', 0)}°C  Uptime: {status.get('uptime_seconds', 0)}s",
        f"Time: {time.strftime('%H:%M:%S')}",
    ]

    y = 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.rectangle(
            [(8, y - 2), (text_width + 12, y + text_height + 2)],
            fill=(0, 0, 0, 160),
        )
        draw.text((10, y), line, fill=(0, 255, 0, 255))
        y += text_height + 6

    out = BytesIO()
    img.save(out, format="JPEG", quality=config.get("jpeg_quality", 70))
    return out.getvalue()


def generate_mjpeg_frames(
    buffer: FrameBuffer,
    overlay: bool = False,
    timeout: float = 2.0,
    config: dict | None = None,
) -> Generator[bytes, None, None]:
    while True:
        frame = buffer.wait_for_frame(timeout=timeout)
        if frame is None:
            yield b""
            continue

        if overlay:
            status = get_system_status()
            frame = render_overlay(frame, status, config or {})

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
            + frame + b"\r\n"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stream.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/stream.py tests/test_stream.py
git commit -m "feat: MJPEG stream generator with Pillow-based status overlay"
```

---

## Task 7: FastAPI Application & Endpoints

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("app.main.camera") as mock_cam:
        mock_cam.is_running = True
        mock_cam.buffer = MagicMock()
        mock_cam.buffer.wait_for_frame.return_value = b"\xff\xd8fake\xff\xd9"

        from app.main import app
        yield TestClient(app)


def test_get_status(client):
    with patch("app.main.get_system_status", return_value={
        "cpu_temperature": 45.0,
        "cpu_usage": 20.0,
        "memory": {"total_mb": 500, "available_mb": 300, "usage_percent": 40.0},
        "wifi": {"ssid": "Test", "signal_dbm": "65", "ip_address": "10.0.0.1"},
        "uptime_seconds": 3600,
    }):
        response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_temperature"] == 45.0
    assert data["camera_running"] is True


def test_get_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["resolution_width"] == 640
    assert data["fps"] == 15


def test_put_config(client):
    with patch("app.main.save_config"):
        response = client.put("/api/config", json={"fps": 10, "overlay": True})
    assert response.status_code == 200
    data = response.json()
    assert data["fps"] == 10
    assert data["overlay"] is True


def test_put_config_invalid_value(client):
    response = client.put("/api/config", json={"fps": 0})
    assert response.status_code == 422


def test_snapshot(client):
    response = client.get("/snapshot")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_stream_returns_mjpeg_content_type(client):
    with patch("app.main.generate_mjpeg_frames", return_value=iter([b"--frame\r\ndata"])):
        response = client.get("/stream")
    assert "multipart/x-mixed-replace" in response.headers["content-type"]


def test_wifi_scan(client):
    from app.wifi import WifiNetwork
    mock_networks = [
        WifiNetwork(ssid="Net1", signal=80, encrypted=True),
        WifiNetwork(ssid="Net2", signal=45, encrypted=False),
    ]
    with patch("app.main.scan_networks", return_value=mock_networks):
        response = client.post("/config/wifi/scan")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ssid"] == "Net1"


def test_wifi_connect_success(client):
    with patch("app.main.connect_to_network", return_value=True):
        response = client.post("/config/wifi", json={"ssid": "Test", "password": "pass"})
    assert response.status_code == 200
    assert response.json()["connected"] is True


def test_wifi_connect_failure(client):
    with patch("app.main.connect_to_network", return_value=False):
        response = client.post("/config/wifi", json={"ssid": "Bad", "password": "wrong"})
    assert response.status_code == 200
    assert response.json()["connected"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write the implementation**

```python
# app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.camera import camera
from app.config import AppConfig, load_config, save_config
from app.status import get_system_status
from app.stream import generate_mjpeg_frames, render_overlay
from app.wifi import scan_networks, connect_to_network, get_saved_networks, delete_network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_config: AppConfig = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    _config = load_config()
    camera.start(
        width=_config.resolution_width,
        height=_config.resolution_height,
        fps=_config.fps,
    )
    logger.info("RaspiZeroCam started")
    yield
    camera.stop()
    logger.info("RaspiZeroCam stopped")


app = FastAPI(title="RaspiZeroCam", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# --- Stream Endpoints ---

@app.get("/stream")
def stream(overlay: bool = Query(False)):
    use_overlay = overlay or _config.overlay
    return StreamingResponse(
        generate_mjpeg_frames(
            camera.buffer,
            overlay=use_overlay,
            config=_config.model_dump() if use_overlay else None,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/snapshot")
def snapshot():
    frame = camera.buffer.wait_for_frame(timeout=2.0)
    if frame is None:
        return Response(status_code=503, content="No frame available")
    return Response(content=frame, media_type="image/jpeg")


@app.get("/snapshot/info")
def snapshot_info():
    frame = camera.buffer.wait_for_frame(timeout=2.0)
    if frame is None:
        return Response(status_code=503, content="No frame available")
    status = get_system_status()
    result = render_overlay(frame, status, _config.model_dump())
    return Response(content=result, media_type="image/jpeg")


# --- REST API ---

@app.get("/api/status")
def api_status():
    status = get_system_status()
    status["camera_running"] = camera.is_running
    return status


@app.get("/api/config")
def api_get_config():
    return _config.model_dump()


@app.put("/api/config")
def api_put_config(updates: dict):
    global _config
    new_config = _config.model_copy(update=updates)
    # Re-validate through Pydantic
    new_config = AppConfig(**new_config.model_dump())

    resolution_changed = (
        new_config.resolution_width != _config.resolution_width
        or new_config.resolution_height != _config.resolution_height
        or new_config.fps != _config.fps
    )

    _config = new_config
    save_config(_config)

    if resolution_changed:
        camera.restart(
            width=_config.resolution_width,
            height=_config.resolution_height,
            fps=_config.fps,
        )

    return _config.model_dump()


# --- WiFi Config ---

class WifiCredentials(BaseModel):
    ssid: str
    password: str


@app.post("/config/wifi/scan")
def wifi_scan():
    networks = scan_networks()
    return [{"ssid": n.ssid, "signal": n.signal, "encrypted": n.encrypted} for n in networks]


@app.post("/config/wifi")
def wifi_connect(creds: WifiCredentials):
    success = connect_to_network(creds.ssid, creds.password)
    return {"connected": success, "ssid": creds.ssid}


@app.get("/config/wifi/saved")
def wifi_saved():
    return get_saved_networks()


@app.delete("/config/wifi/{name}")
def wifi_delete(name: str):
    success = delete_network(name)
    return {"deleted": success, "name": name}


# --- Config Portal ---

@app.get("/config")
def config_portal():
    from fastapi.responses import FileResponse
    return FileResponse("app/static/index.html")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: FastAPI application with stream, snapshot, config, and WiFi endpoints"
```

---

## Task 8: Config Portal Web-UI

**Files:**
- Create: `app/static/index.html`

- [ ] **Step 1: Create the single-file config portal**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RaspiZeroCam</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 16px; }
        h1 { font-size: 1.3em; margin-bottom: 16px; color: #0ff; }
        h2 { font-size: 1.1em; margin: 16px 0 8px; color: #0ff; border-bottom: 1px solid #333; padding-bottom: 4px; }

        .card { background: #16213e; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
        .preview { width: 100%; border-radius: 4px; background: #000; }

        label { display: block; margin: 8px 0 4px; font-size: 0.85em; color: #aaa; }
        select, input[type="range"], input[type="text"], input[type="password"] {
            width: 100%; padding: 8px; border: 1px solid #333; border-radius: 4px;
            background: #0f3460; color: #eee; font-size: 0.9em;
        }
        input[type="range"] { padding: 4px 0; }
        .range-value { font-size: 0.85em; color: #0ff; float: right; }

        button {
            padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;
            background: #0ff; color: #1a1a2e; font-weight: bold; font-size: 0.9em; margin: 4px 4px 4px 0;
        }
        button:hover { background: #00cccc; }
        button.danger { background: #e94560; color: #fff; }
        button.danger:hover { background: #c73e54; }

        .toggle { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
        .toggle input { width: auto; }

        .wifi-list { list-style: none; }
        .wifi-list li {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px; border-bottom: 1px solid #333; cursor: pointer;
        }
        .wifi-list li:hover { background: #0f3460; }
        .signal { font-size: 0.8em; color: #aaa; }
        .encrypted::after { content: " 🔒"; font-size: 0.8em; }

        .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .status-item { font-size: 0.85em; }
        .status-label { color: #aaa; }
        .status-value { color: #0ff; font-weight: bold; }

        .saved-list { list-style: none; }
        .saved-list li { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #222; }

        #msg { padding: 8px; margin: 8px 0; border-radius: 4px; display: none; font-size: 0.85em; }
        #msg.ok { display: block; background: #0a3d2a; color: #0f8; }
        #msg.err { display: block; background: #3d0a0a; color: #f55; }
    </style>
</head>
<body>
    <h1>RaspiZeroCam</h1>
    <div id="msg"></div>

    <div class="card">
        <h2>Live Preview</h2>
        <img class="preview" id="preview" src="/stream" alt="Camera stream">
    </div>

    <div class="card">
        <h2>Camera Settings</h2>
        <label>Resolution</label>
        <select id="resolution">
            <option value="320x240">320x240</option>
            <option value="640x480" selected>640x480</option>
            <option value="800x600">800x600</option>
            <option value="1280x720">1280x720</option>
        </select>

        <label>FPS <span class="range-value" id="fpsVal">15</span></label>
        <input type="range" id="fps" min="5" max="30" value="15">

        <label>JPEG Quality <span class="range-value" id="qualityVal">70</span></label>
        <input type="range" id="quality" min="30" max="95" value="70">

        <div class="toggle">
            <input type="checkbox" id="rotation">
            <label for="rotation" style="display:inline; margin:0;">Rotate 180°</label>
        </div>
        <div class="toggle">
            <input type="checkbox" id="overlay">
            <label for="overlay" style="display:inline; margin:0;">Status Overlay</label>
        </div>
        <button onclick="saveConfig()">Apply</button>
    </div>

    <div class="card">
        <h2>WiFi Configuration</h2>
        <button onclick="scanWifi()">Scan Networks</button>
        <ul class="wifi-list" id="wifiList"></ul>
        <label>SSID</label>
        <input type="text" id="ssid" placeholder="Network name">
        <label>Password</label>
        <input type="password" id="wifiPass" placeholder="Password">
        <button onclick="connectWifi()">Connect</button>

        <h2>Saved Networks</h2>
        <ul class="saved-list" id="savedList"></ul>
        <button onclick="loadSaved()">Refresh</button>
    </div>

    <div class="card">
        <h2>System Status</h2>
        <div class="status-grid" id="statusGrid"></div>
        <button onclick="loadStatus()">Refresh</button>
    </div>

<script>
const $ = id => document.getElementById(id);

function msg(text, ok) {
    const el = $('msg');
    el.textContent = text;
    el.className = ok ? 'ok' : 'err';
    setTimeout(() => el.style.display = 'none', 3000);
}

async function loadConfig() {
    const r = await fetch('/api/config');
    const c = await r.json();
    $('resolution').value = c.resolution_width + 'x' + c.resolution_height;
    $('fps').value = c.fps; $('fpsVal').textContent = c.fps;
    $('quality').value = c.jpeg_quality; $('qualityVal').textContent = c.jpeg_quality;
    $('rotation').checked = c.rotation === 180;
    $('overlay').checked = c.overlay;
}

async function saveConfig() {
    const res = $('resolution').value.split('x');
    const body = {
        resolution_width: parseInt(res[0]),
        resolution_height: parseInt(res[1]),
        fps: parseInt($('fps').value),
        jpeg_quality: parseInt($('quality').value),
        rotation: $('rotation').checked ? 180 : 0,
        overlay: $('overlay').checked,
    };
    const r = await fetch('/api/config', { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    if (r.ok) {
        msg('Settings applied', true);
        $('preview').src = '/stream?overlay=' + body.overlay + '&t=' + Date.now();
    } else {
        msg('Failed to apply settings', false);
    }
}

async function scanWifi() {
    const r = await fetch('/config/wifi/scan', { method: 'POST' });
    const nets = await r.json();
    $('wifiList').innerHTML = nets.map(n =>
        `<li onclick="$('ssid').value='${n.ssid}'">
            <span class="${n.encrypted ? 'encrypted' : ''}">${n.ssid}</span>
            <span class="signal">${n.signal}%</span>
        </li>`
    ).join('');
}

async function connectWifi() {
    const body = { ssid: $('ssid').value, password: $('wifiPass').value };
    const r = await fetch('/config/wifi', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    const d = await r.json();
    msg(d.connected ? 'Connected to ' + d.ssid : 'Connection failed', d.connected);
}

async function loadSaved() {
    const r = await fetch('/config/wifi/saved');
    const nets = await r.json();
    $('savedList').innerHTML = nets.map(n =>
        `<li><span>${n}</span><button class="danger" onclick="deleteWifi('${n}')">Delete</button></li>`
    ).join('');
}

async function deleteWifi(name) {
    await fetch('/config/wifi/' + encodeURIComponent(name), { method: 'DELETE' });
    loadSaved();
}

async function loadStatus() {
    const r = await fetch('/api/status');
    const s = await r.json();
    $('statusGrid').innerHTML = `
        <div class="status-item"><span class="status-label">CPU Temp</span><br><span class="status-value">${s.cpu_temperature}°C</span></div>
        <div class="status-item"><span class="status-label">CPU Usage</span><br><span class="status-value">${s.cpu_usage}%</span></div>
        <div class="status-item"><span class="status-label">RAM</span><br><span class="status-value">${s.memory.usage_percent}% (${s.memory.available_mb}MB free)</span></div>
        <div class="status-item"><span class="status-label">WiFi</span><br><span class="status-value">${s.wifi.ssid || 'N/A'} (${s.wifi.signal_dbm} dBm)</span></div>
        <div class="status-item"><span class="status-label">IP</span><br><span class="status-value">${s.wifi.ip_address || 'N/A'}</span></div>
        <div class="status-item"><span class="status-label">Uptime</span><br><span class="status-value">${Math.floor(s.uptime_seconds / 60)}m</span></div>
        <div class="status-item"><span class="status-label">Camera</span><br><span class="status-value">${s.camera_running ? 'Running' : 'Stopped'}</span></div>
        <div class="status-item"><span class="status-label">Stream Clients</span><br><span class="status-value">${s.stream_clients || 0}</span></div>
    `;
}

$('fps').oninput = () => $('fpsVal').textContent = $('fps').value;
$('quality').oninput = () => $('qualityVal').textContent = $('quality').value;

loadConfig();
loadStatus();
loadSaved();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify the file loads in main.py**

Run: `python -c "from fastapi.staticfiles import StaticFiles; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "feat: config portal web-UI with live preview, WiFi config, and status"
```

---

## Task 9: WiFi Boot Sequence & AP Fallback Integration

**Files:**
- Modify: `app/main.py` (add startup WiFi logic)
- Modify: `app/wifi.py` (add `ensure_connected` function)

- [ ] **Step 1: Add ensure_connected to wifi.py**

Add this function at the end of `app/wifi.py`:

```python
import time
import logging

logger = logging.getLogger(__name__)

AP_TIMEOUT_SECONDS = 300  # 5 minutes


def ensure_connected() -> bool:
    """Try saved networks first. If none connect, start AP and wait for config."""
    saved = get_saved_networks()
    if saved:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("yes:"):
                logger.info(f"Already connected to {line.split(':')[1]}")
                return True

        for network in saved:
            logger.info(f"Trying saved network: {network}")
            res = subprocess.run(
                ["nmcli", "connection", "up", network],
                capture_output=True, text=True
            )
            if res.returncode == 0:
                logger.info(f"Connected to {network}")
                return True

    logger.info("No known network found — starting AP fallback")
    start_ap()

    start_time = time.time()
    while time.time() - start_time < AP_TIMEOUT_SECONDS:
        time.sleep(10)
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("yes:") and "RaspiZeroCam" not in line:
                logger.info("Connected via config portal")
                stop_ap()
                return True

    logger.info("AP timeout — retrying network scan")
    stop_ap()
    return False
```

- [ ] **Step 2: Update main.py lifespan to use ensure_connected**

Replace the lifespan function in `app/main.py`:

```python
from app.wifi import scan_networks, connect_to_network, get_saved_networks, delete_network, ensure_connected

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    _config = load_config()

    # WiFi boot sequence (non-blocking for AP mode — portal still needs to serve)
    import threading
    def wifi_boot():
        while not ensure_connected():
            pass  # Retry until connected
    wifi_thread = threading.Thread(target=wifi_boot, daemon=True)
    wifi_thread.start()

    camera.start(
        width=_config.resolution_width,
        height=_config.resolution_height,
        fps=_config.fps,
    )
    logger.info("RaspiZeroCam started")
    yield
    camera.stop()
    logger.info("RaspiZeroCam stopped")
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/wifi.py app/main.py
git commit -m "feat: WiFi boot sequence with AP fallback and auto-retry"
```

---

## Task 10: CPU Auto-Throttle

**Files:**
- Modify: `app/camera.py` (add throttle method)
- Modify: `app/main.py` (add background throttle thread)

The spec requires: "If CPU is sustained >90%, FPS is automatically reduced to keep the stream stable. Reported in `/api/status`."

- [ ] **Step 1: Add throttle capability to Camera**

Add to the `Camera` class in `app/camera.py`:

```python
    def throttle_fps(self, new_fps: int) -> None:
        if not self._picam2 or not self._running:
            return
        self._picam2.set_controls({"FrameRate": float(new_fps)})
        logger.info(f"Throttled FPS to {new_fps}")
```

- [ ] **Step 2: Add throttle monitor to main.py**

Add this after the WiFi boot thread in the `lifespan` function in `app/main.py`:

```python
    # CPU auto-throttle: reduce FPS if CPU sustained >90%
    _throttled = False

    def cpu_throttle_monitor():
        nonlocal _throttled
        while True:
            time.sleep(5)
            usage = get_system_status()["cpu_usage"]
            if usage > 90 and not _throttled:
                reduced_fps = max(5, _config.fps // 2)
                camera.throttle_fps(reduced_fps)
                _throttled = True
                logger.warning(f"CPU at {usage}% — throttled FPS to {reduced_fps}")
            elif usage < 70 and _throttled:
                camera.throttle_fps(_config.fps)
                _throttled = False
                logger.info(f"CPU at {usage}% — restored FPS to {_config.fps}")

    import time
    throttle_thread = threading.Thread(target=cpu_throttle_monitor, daemon=True)
    throttle_thread.start()
```

- [ ] **Step 3: Add throttle status to /api/status**

In `app/main.py`, add a module-level variable and expose it in the status endpoint:

```python
_throttled = False  # Move to module level

@app.get("/api/status")
def api_status():
    status = get_system_status()
    status["camera_running"] = camera.is_running
    status["fps_throttled"] = _throttled
    return status
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/camera.py app/main.py
git commit -m "feat: auto-throttle FPS when CPU usage exceeds 90%"
```

---

## Task 11: systemd Service & Install Script

**Files:**
- Create: `raspizerocam.service`
- Create: `install.sh`

- [ ] **Step 1: Create the systemd unit file**

```ini
# raspizerocam.service
[Unit]
Description=RaspiZeroCam Streaming Server
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/raspizerocam
ExecStart=/opt/raspizerocam/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create the install script**

```bash
#!/bin/bash
# install.sh — Setup RaspiZeroCam on Raspberry Pi Zero
set -e

echo "=== RaspiZeroCam Installer ==="

# Install system dependencies
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libcamera-apps python3-picamera2 network-manager

# Ensure NetworkManager manages wlan0
echo "Configuring NetworkManager..."
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager

# Create install directory
INSTALL_DIR="/opt/raspizerocam"
echo "Setting up ${INSTALL_DIR}..."
sudo mkdir -p ${INSTALL_DIR}
sudo cp -r . ${INSTALL_DIR}/

# Create virtual environment
echo "Creating Python venv..."
cd ${INSTALL_DIR}
python3 -m venv venv --system-site-packages
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Install systemd service
echo "Installing systemd service..."
sudo cp raspizerocam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable raspizerocam
sudo systemctl start raspizerocam

echo "=== Installation complete ==="
echo "Stream available at http://$(hostname -I | awk '{print $1}'):8080/stream"
echo "Config portal at http://$(hostname -I | awk '{print $1}'):8080/config"
```

- [ ] **Step 3: Make install.sh executable and commit**

```bash
chmod +x install.sh
git add raspizerocam.service install.sh
git commit -m "feat: systemd service and install script for Pi Zero deployment"
```

---

## Task 12: README & Final Integration Test

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md**

```markdown
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
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "feat: README with quickstart, endpoints, and dev workflow"
```

---

## Task 13: Deploy to Pi Zero & Manual Verification

- [ ] **Step 1: Create GitHub repository**

```bash
gh repo create andreasschegg/RaspiZeroCam --public --source=. --push
```

- [ ] **Step 2: SSH to Pi Zero and install**

```bash
ssh <pi-zero-hostname> "git clone https://github.com/andreasschegg/RaspiZeroCam.git && cd RaspiZeroCam && ./install.sh"
```

- [ ] **Step 3: Verify stream in browser**

Open `http://<pi-zero-ip>:8080/stream` in browser — should show live camera feed.

- [ ] **Step 4: Verify snapshot**

Open `http://<pi-zero-ip>:8080/snapshot` — should show single JPEG.

- [ ] **Step 5: Verify snapshot/info**

Open `http://<pi-zero-ip>:8080/snapshot/info` — should show JPEG with status overlay.

- [ ] **Step 6: Verify config portal**

Open `http://<pi-zero-ip>:8080/config` — should show web-UI with live preview, camera settings, WiFi config, and status.

- [ ] **Step 7: Verify API**

```bash
curl http://<pi-zero-ip>:8080/api/status | python -m json.tool
curl http://<pi-zero-ip>:8080/api/config | python -m json.tool
```

- [ ] **Step 8: Commit any fixes from manual testing**

```bash
git add -A && git commit -m "fix: adjustments from manual testing on Pi Zero"
git push origin main
```
