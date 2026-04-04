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
